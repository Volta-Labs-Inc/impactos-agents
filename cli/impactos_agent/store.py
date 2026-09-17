"""The ``impactos store ...`` subcommands: per-user login, provisioning, and the
thin access wrappers.

Design constraints (issue #7 / 6a), all enforced here:

* Every network call uses the Python standard library (``urllib``) — no third
  party HTTP client, no model calls.
* A user signs in through Supabase Auth with the project's *publishable* key and
  receives a per-user session; the session is refreshed on a 401 and retried
  once. No service-role key is ever minted, held, printed or written.
* Provisioning applies migrations through the Supabase *management API* using the
  personal access token that ``supabase login`` keeps in the operating-system
  keychain. It refuses to run unless a store route choice is recorded, and
  refuses any secret passed on the command line or through an inline environment
  variable. It never holds a service-role key or a database password.

This module writes only to the git-ignored ``workspace/config.json`` and prints
redacted output (identities and migration names, never keys or tokens).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import paths
from .result import Result

# ---- credential locations (documented in docs/store.md) ------------------- #
# The Supabase CLI stores the personal access token in the OS keychain under this
# service/account (macOS Keychain / libsecret). We read it only at provision time
# and never print it.
SUPABASE_KEYCHAIN_SERVICE = "Supabase CLI"
SUPABASE_KEYCHAIN_ACCOUNT = "access-token"

MANAGEMENT_API = "https://api.supabase.com"

# Route choice must be recorded here before provisioning is allowed.
ROUTES_RELPATH = "operating-notes/routes.md"
# An explicit, recorded decision that the optional store is in use.
ROUTE_MARKER = re.compile(r"(?im)^\s*store[_ -]?route\s*[:=]\s*(enabled|adopt|move|yes|chosen)\b")

# Argument / environment names that must never carry a secret into provisioning.
SECRET_ARG_TOKENS = (
    "service-role", "service_role", "service-key", "service_key",
    "db-password", "db_password", "database-password", "database_password",
    "secret-key", "secret_key",
)
SECRET_ENV_NAMES = (
    "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY", "SERVICE_ROLE_KEY",
    "SUPABASE_DB_PASSWORD", "SUPABASE_DB_URL", "PGPASSWORD", "DATABASE_URL",
    "SUPABASE_SECRET_KEY",
)


# --------------------------------------------------------------------------- #
# Config (merged into workspace/config.json under a "store" key).
# --------------------------------------------------------------------------- #
def _load_config(project_root: Path) -> Dict[str, Any]:
    config_path = paths.config_path(project_root)
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_config(project_root: Path, config: Dict[str, Any]) -> None:
    config_path = paths.config_path(project_root)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _store_section(config: Dict[str, Any]) -> Dict[str, Any]:
    return config.setdefault("store", {})


# --------------------------------------------------------------------------- #
# stdlib HTTP helper.
# --------------------------------------------------------------------------- #
def _http(method: str, url: str, headers: Dict[str, str], body: Optional[dict] = None
          ) -> Tuple[int, bytes]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310 (trusted host)
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _auth_headers(publishable_key: str, access_token: Optional[str] = None) -> Dict[str, str]:
    headers = {"apikey": publishable_key, "Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


# --------------------------------------------------------------------------- #
# Secret smuggling guards.
# --------------------------------------------------------------------------- #
def _argv_secret(argv: List[str]) -> Optional[str]:
    for token in argv:
        lowered = token.lower()
        for needle in SECRET_ARG_TOKENS:
            if needle in lowered:
                return token.split("=", 1)[0]
    return None


def _env_secret(environ: Dict[str, str]) -> Optional[str]:
    for name in SECRET_ENV_NAMES:
        if environ.get(name):
            return name
    return None


# --------------------------------------------------------------------------- #
# login
# --------------------------------------------------------------------------- #
def _refresh_session(store: Dict[str, Any]) -> bool:
    """Exchange the stored refresh token for a new session. Returns success."""
    session = store.get("session") or {}
    refresh_token = session.get("refresh_token")
    if not (store.get("api_url") and store.get("publishable_key") and refresh_token):
        return False
    url = f"{store['api_url']}/auth/v1/token?grant_type=refresh_token"
    status, body = _http("POST", url, _auth_headers(store["publishable_key"]),
                         {"refresh_token": refresh_token})
    if status != 200:
        return False
    payload = json.loads(body)
    session["access_token"] = payload.get("access_token")
    session["refresh_token"] = payload.get("refresh_token", refresh_token)
    store["session"] = session
    return True


def authed_request(project_root: Path, method: str, path: str, body: Optional[dict] = None
                   ) -> Tuple[int, bytes]:
    """A REST call as the signed-in user that refreshes once on a 401."""
    config = _load_config(project_root)
    store = _store_section(config)
    session = store.get("session") or {}
    url = f"{store['api_url']}{path}"
    status, data = _http(method, url,
                         _auth_headers(store["publishable_key"], session.get("access_token")), body)
    if status == 401 and _refresh_session(store):
        _save_config(project_root, config)
        session = store.get("session") or {}
        status, data = _http(method, url,
                             _auth_headers(store["publishable_key"], session.get("access_token")), body)
    return status, data


def login(project_root: Path, args) -> Result:
    result = Result("store login")
    config = _load_config(project_root)
    store = _store_section(config)

    api_url = args.api_url or store.get("api_url")
    publishable_key = args.publishable_key or store.get("publishable_key")
    if not api_url or not publishable_key:
        result.add_error("no project configured; run `impactos store provision` first "
                         "or pass --api-url and --publishable-key")
        return result
    store["api_url"] = api_url
    store["publishable_key"] = publishable_key

    if args.otp_request:
        status, body = _http("POST", f"{api_url}/auth/v1/otp",
                             _auth_headers(publishable_key), {"email": args.email})
        if status not in (200, 204):
            result.add_error(f"could not send login code (status {status})")
            return result
        result.summary = f"Login code sent to {args.email}. Re-run with --token <code>."
        return result

    if args.token:
        status, body = _http("POST", f"{api_url}/auth/v1/verify",
                             _auth_headers(publishable_key),
                             {"type": "email", "email": args.email, "token": args.token})
    elif args.password is not None:
        status, body = _http("POST", f"{api_url}/auth/v1/token?grant_type=password",
                             _auth_headers(publishable_key),
                             {"email": args.email, "password": args.password})
    else:
        result.add_error("provide --password (fixture) or --otp-request then --token (real use)")
        return result

    if status != 200:
        result.add_error(f"sign-in failed (status {status})")
        return result

    payload = json.loads(body)
    user = payload.get("user") or {}
    store["session"] = {
        "access_token": payload.get("access_token"),
        "refresh_token": payload.get("refresh_token"),
        "user_id": user.get("id"),
        "email": user.get("email"),
    }
    _save_config(project_root, config)

    roles = _fetch_roles(project_root)
    result.data = {
        "email": user.get("email"),
        "user_id": user.get("id"),
        "roles": roles,
        "service_role_used": False,
    }
    result.summary = f"Signed in as {user.get('email')} ({', '.join(roles) or 'no active role'})."
    return result


def _fetch_roles(project_root: Path) -> List[str]:
    status, body = authed_request(
        project_root, "GET",
        "/rest/v1/user_role?select=ends_at,app_role(name)")
    if status != 200:
        return []
    rows = json.loads(body)
    names = []
    for row in rows:
        role = (row.get("app_role") or {}).get("name")
        if role:
            names.append(role)
    return sorted(set(names))


# --------------------------------------------------------------------------- #
# provision
# --------------------------------------------------------------------------- #
def _route_recorded(project_root: Path) -> bool:
    routes = project_root / ROUTES_RELPATH
    if not routes.exists():
        return False
    return bool(ROUTE_MARKER.search(routes.read_text(encoding="utf-8")))


def _read_personal_access_token() -> Optional[str]:
    """Read the Supabase CLI personal access token from the OS keychain. Never
    printed. Returns None if unavailable."""
    if sys.platform == "darwin":
        cmd = ["security", "find-generic-password",
               "-s", SUPABASE_KEYCHAIN_SERVICE, "-a", SUPABASE_KEYCHAIN_ACCOUNT, "-w"]
    else:
        cmd = ["secret-tool", "lookup", "service", SUPABASE_KEYCHAIN_SERVICE,
               "account", SUPABASE_KEYCHAIN_ACCOUNT]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
        return out or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _management_query(ref: str, token: str, sql: str) -> Tuple[int, bytes]:
    url = f"{MANAGEMENT_API}/v1/projects/{ref}/database/query"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return _http("POST", url, headers, {"query": sql})


def _fetch_publishable_key(ref: str, token: str) -> Optional[str]:
    url = f"{MANAGEMENT_API}/v1/projects/{ref}/api-keys?reveal=true"
    headers = {"Authorization": f"Bearer {token}"}
    status, body = _http("GET", url, headers)
    if status != 200:
        return None
    for key in json.loads(body):
        name = (key.get("name") or "").lower()
        key_type = (key.get("type") or "").lower()
        if name in ("anon", "publishable") or key_type == "publishable":
            return key.get("api_key") or key.get("api_key_secret")
    return None


def provision(project_root: Path, args, argv: List[str], environ: Dict[str, str]) -> Result:
    result = Result("store provision")

    smuggled_arg = _argv_secret(argv)
    if smuggled_arg:
        result.add_error(f"refusing: a secret must never be passed on the command line "
                         f"(saw {smuggled_arg!r}). Use `supabase login` (keychain) instead.")
        return result
    smuggled_env = _env_secret(environ)
    if smuggled_env:
        result.add_error(f"refusing: a secret must never be passed inline through the environment "
                         f"(saw {smuggled_env}). Use `supabase login` (keychain) instead.")
        return result

    if not _route_recorded(project_root):
        result.add_error(f"refusing: no store route choice recorded in {ROUTES_RELPATH} "
                         f"(add a line like 'store_route: enabled'). Provision only after the "
                         f"route is chosen.")
        return result

    ref = args.project_ref
    if not ref:
        result.add_error("provide --project-ref (the Supabase project reference)")
        return result

    token = _read_personal_access_token()
    if not token:
        result.add_error("no Supabase personal access token found in the OS keychain; "
                         "run `supabase login` first")
        return result

    applied: List[str] = []
    migration_files = sorted((project_root / "store" / "migrations").glob("*.sql"))
    if not migration_files:
        result.add_error("no migrations found under store/migrations/")
        return result

    for migration in migration_files:
        sql = migration.read_text(encoding="utf-8")
        status, body = _management_query(ref, token, sql)
        if status not in (200, 201):
            # Redact: never echo the response body (may carry connection detail).
            result.add_error(f"applying {migration.name} failed (status {status})")
            result.data = {"applied": applied, "project_ref": ref}
            return result
        applied.append(migration.name)

    publishable_key = _fetch_publishable_key(ref, token)

    config = _load_config(project_root)
    store = _store_section(config)
    store["project_ref"] = ref
    store["api_url"] = args.api_url or f"https://{ref}.supabase.co"
    if publishable_key:
        store["publishable_key"] = publishable_key
    _save_config(project_root, config)

    result.data = {
        "project_ref": ref,
        "applied": applied,
        "publishable_key_recorded": bool(publishable_key),
        "service_role_used": False,
        "db_password_used": False,
    }
    result.summary = (f"Provisioned project {ref}: applied {len(applied)} migration(s). "
                      f"No service-role key or database password was used.")
    return result


# --------------------------------------------------------------------------- #
# access end / access check (thin wrappers over the signed-in session)
# --------------------------------------------------------------------------- #
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def access_end(project_root: Path, args) -> Result:
    result = Result("store access end")
    if not UUID_RE.match(args.user or ""):
        result.add_error("provide a valid --user UUID")
        return result

    status, body = authed_request(
        project_root, "GET", f"/rest/v1/app_role?select=id&name=eq.{args.role}")
    if status != 200 or not json.loads(body):
        result.add_error(f"could not resolve the {args.role!r} role (status {status})")
        return result
    role_id = json.loads(body)[0]["id"]

    ends_at = args.at or "now()"
    patch_path = f"/rest/v1/user_role?user_id=eq.{args.user}&role_id=eq.{role_id}"
    status, body = authed_request(
        project_root, "PATCH", patch_path, {"ends_at": ends_at})
    if status not in (200, 204):
        result.add_error(f"could not end the role (status {status}); a staff or active "
                         f"helper session is required")
        return result
    result.summary = f"Ended {args.role} for {args.user} at {ends_at}."
    result.data = {"user": args.user, "role": args.role, "ends_at": ends_at}
    return result


def access_check(project_root: Path, args) -> Result:
    """Explicit access answer (SR-21): 'access denied' rather than an empty read."""
    result = Result("store access check")
    if not UUID_RE.match(args.company or ""):
        result.add_error(f"unknown company: {args.company!r} is not a valid company reference")
        result.summary = "Unknown company."
        return result

    status, body = authed_request(
        project_root, "POST", "/rest/v1/rpc/can_see_company", {"p_company_id": args.company})
    if status != 200:
        result.add_error(f"access check failed (status {status}); sign in first")
        return result
    allowed = json.loads(body)
    if allowed is True:
        result.summary = f"Access granted to company {args.company}."
        result.data = {"company": args.company, "access": "granted"}
        return result
    result.add_error(f"access denied to company {args.company}")
    result.summary = "Access denied."
    result.data = {"company": args.company, "access": "denied"}
    return result
