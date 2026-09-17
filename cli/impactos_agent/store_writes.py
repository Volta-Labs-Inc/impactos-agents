"""The ``impactos store`` write path (child 6b): preview-then-confirm writes,
retraction, and the founder-queue review.

Design (issue #8, the reviewer-agreed simplification of the Coach OS token stack):

* ``store write`` computes one canonical request hash over the proposed facts and
  their provenance, writes ``workspace/state/previews/<hash>.json`` with a ten
  minute expiry, and prints the preview. Nothing is written to the store.
* ``store write --confirm <hash>`` applies only if that preview exists, is
  unexpired, and the current inputs still hash to the same value. It calls one
  database function, ``apply_write_batch``, whose first act is to claim a write
  batch whose id is derived from the request hash; a second confirm of the same
  hash finds the batch already present and is a no-op. The whole write is one
  transaction, run under the signed-in user's session, so 6a's policies decide
  what may be written.
* ``store retract`` records a retraction row (actor and time from the session);
  the original fact is untouched, and the store reader excludes it from every
  export and brief thereafter.
* ``store review`` accepts a founder submission through the guarded
  ``accept_submission`` function, or rejects it.

The request hash is deterministic over content only (never over the preview's own
timestamps), so re-previewing the same inputs yields the same hash and the same
batch.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import paths
from . import store as store_mod
from .result import Result

PREVIEW_TTL_SECONDS = 600  # ten minutes (issue #8)

# The fact tables the write path may target. Must match the whitelist enforced by
# app._insert_fact in migration 0004; keeping it here too gives an early, clear
# refusal before any network call.
WRITABLE_TABLES = (
    "company_update", "funding_event", "team_member_period",
    "milestone_position", "milestone_target", "interaction", "membership",
)

# Money fields stored as amount + <field>_currency; a {"amount","currency"} value
# is flattened before it reaches the numeric column.
_MONEY_FIELDS = {
    "company_update": ("annual_revenue", "export_revenue", "lifetime_revenue"),
    "funding_event": ("amount",),
}

# A "<entity>_ref" (source id) is translated to "<entity>_id" (database key).
_REF_ENTITY = {
    "company_ref": ("company", "company_id"),
    "cohort_ref": ("cohort", "cohort_id"),
    "person_ref": ("person", "person_id"),
    "program_ref": ("program", "program_id"),
}


# --------------------------------------------------------------------------- #
# Canonical proposal + hashing
# --------------------------------------------------------------------------- #
def _canonical_facts(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The deterministic list of proposed facts from a records document.

    One entry per writable record, ordered by table then identity, each carrying
    the record fields (money flattened) and the provenance the record already
    holds. Ordering and key-sorting make the hash stable.
    """
    records = document.get("records", {})
    facts: List[Dict[str, Any]] = []
    for table in WRITABLE_TABLES:
        for record in sorted(records.get(table, []), key=lambda r: str(r.get("identity"))):
            fields = _flatten_money(table, dict(record.get("fields", {})))
            facts.append({
                "fact_table": table,
                "identity": record.get("identity"),
                "record": fields,
                "provenance": record.get("provenance", {}),
            })
    return facts


def _flatten_money(table: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    for money_field in _MONEY_FIELDS.get(table, ()):  # noqa: B007
        value = fields.get(money_field)
        if isinstance(value, dict):
            fields[money_field] = value.get("amount")
            currency = value.get("currency")
            if currency is not None:
                fields[f"{money_field}_currency"] = currency
    return fields


def _request_hash(facts: List[Dict[str, Any]]) -> str:
    canonical = json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _batch_uuid(request_hash: str) -> str:
    """A stable UUID derived from the request hash (its first 128 bits). The
    write_batch primary key is a uuid, so the hash is mapped 1:1 into that space;
    the same request always claims the same batch, which is what makes replay a
    no-op."""
    return str(uuid.UUID(request_hash[:32]))


# --------------------------------------------------------------------------- #
# Records resolution
# --------------------------------------------------------------------------- #
def _load_document(project_root: Path, args) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if getattr(args, "records", None):
        records_path = Path(args.records)
    elif getattr(args, "period", None):
        records_path = paths.workspace_dir(project_root) / "state" / args.period / "records.json"
    else:
        return None, "provide --records <path> or --period <label>"
    if not records_path.exists():
        return None, f"records not found: {records_path}"
    return json.loads(records_path.read_text(encoding="utf-8")), None


def _preview_path(project_root: Path, request_hash: str) -> Path:
    return paths.workspace_dir(project_root) / "state" / "previews" / f"{request_hash}.json"


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# --------------------------------------------------------------------------- #
# write (preview) / write --confirm (apply)
# --------------------------------------------------------------------------- #
def write(project_root: Path, args,
          rpc: Optional[Callable[[str, dict], Tuple[int, bytes]]] = None,
          get_rows: Optional[Callable[[str, str], List[Dict[str, Any]]]] = None) -> Result:
    if getattr(args, "confirm", None):
        return _confirm(project_root, args, rpc=rpc, get_rows=get_rows)
    return _preview(project_root, args)


def _preview(project_root: Path, args) -> Result:
    result = Result("store write")
    document, error = _load_document(project_root, args)
    if error:
        result.add_error(error)
        return result

    facts = _canonical_facts(document)
    if not facts:
        result.add_error("no writable facts in the records document (nothing to preview)")
        return result

    request_hash = _request_hash(facts)
    created = _now()
    expires = created + datetime.timedelta(seconds=PREVIEW_TTL_SECONDS)
    preview = {
        "request_hash": request_hash,
        "batch_id": _batch_uuid(request_hash),
        "created_at": created.isoformat(),
        "expires_at": expires.isoformat(),
        "records_path": str(Path(args.records) if getattr(args, "records", None)
                            else paths.workspace_dir(project_root) / "state" / args.period / "records.json"),
        "period": document.get("period"),
        "note": getattr(args, "note", None),
        "facts": facts,
    }
    preview_path = _preview_path(project_root, request_hash)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_text(json.dumps(preview, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                            encoding="utf-8")

    summary_by_table: Dict[str, int] = {}
    for fact in facts:
        summary_by_table[fact["fact_table"]] = summary_by_table.get(fact["fact_table"], 0) + 1

    result.data = {
        "request_hash": request_hash,
        "batch_id": preview["batch_id"],
        "preview_path": str(preview_path),
        "expires_at": preview["expires_at"],
        "fact_count": len(facts),
        "facts_by_table": summary_by_table,
        "facts": [{"fact_table": f["fact_table"], "identity": f["identity"]} for f in facts],
    }
    counts = ", ".join(f"{t}={n}" for t, n in sorted(summary_by_table.items()))
    result.summary = (
        f"Preview {request_hash[:12]}: {len(facts)} fact(s) ({counts}). "
        f"Expires {preview['expires_at']}. Apply with: "
        f"impactos store write --confirm {request_hash}"
    )
    return result


def _confirm(project_root: Path, args,
             rpc: Optional[Callable[[str, dict], Tuple[int, bytes]]] = None,
             get_rows: Optional[Callable[[str, str], List[Dict[str, Any]]]] = None) -> Result:
    result = Result("store write --confirm")
    request_hash = args.confirm
    preview_path = _preview_path(project_root, request_hash)
    if not preview_path.exists():
        result.add_error(f"no preview for {request_hash[:12]}…; run `impactos store write` first")
        result.summary = "Confirm refused: missing preview."
        return result

    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    expires_at = datetime.datetime.fromisoformat(preview["expires_at"])
    if _now() > expires_at:
        result.add_error(f"preview {request_hash[:12]}… expired at {preview['expires_at']}; re-run `impactos store write`")
        result.summary = "Confirm refused: expired preview."
        return result

    # The current inputs must still hash to the same value.
    records_path = Path(preview["records_path"])
    if not records_path.exists():
        result.add_error(f"the records the preview was built from are gone: {records_path}")
        result.summary = "Confirm refused: inputs missing."
        return result
    current = _request_hash(_canonical_facts(json.loads(records_path.read_text(encoding="utf-8"))))
    if current != request_hash:
        result.add_error("inputs changed since the preview (they now hash differently); re-run `impactos store write`")
        result.summary = "Confirm refused: inputs changed."
        return result

    facts, resolve_error = _resolve_facts(project_root, preview["facts"], get_rows=get_rows)
    if resolve_error:
        result.add_error(resolve_error)
        result.summary = "Confirm refused: could not resolve references."
        return result

    company_ids = {f["record"].get("company_id") for f in facts if f["record"].get("company_id")}
    p_company_id = next(iter(company_ids)) if len(company_ids) == 1 else None

    status, body = _call_apply(project_root, preview["batch_id"], p_company_id,
                               preview.get("note"), facts, rpc=rpc)
    if status not in (200, 201):
        result.add_error(f"the store refused the write (status {status}); a staff or helper session is required")
        result.summary = "Confirm refused by the store."
        return result

    payload = _first(json.loads(body))
    applied = (payload or {}).get("status")
    result.data = {
        "request_hash": request_hash,
        "batch_id": preview["batch_id"],
        "store_status": applied,
        "fact_count": (payload or {}).get("fact_count", 0),
        "replayed_noop": applied == "noop",
    }
    if applied == "noop":
        result.summary = (f"Already applied: batch {preview['batch_id']} exists, so this confirm wrote "
                          f"nothing (replay no-op).")
    else:
        result.summary = (f"Applied batch {preview['batch_id']}: {(payload or {}).get('fact_count', 0)} "
                          f"fact(s) written under your session.")
    return result


def _resolve_facts(project_root: Path, preview_facts: List[Dict[str, Any]],
                   get_rows: Optional[Callable[[str, str], List[Dict[str, Any]]]] = None
                   ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Translate every ``*_ref`` source id in the proposed records into the
    matching database key by reading the parent tables from the store."""
    get_rows = get_rows or _default_get_rows(project_root)
    needed_entities = set()
    for fact in preview_facts:
        for key in fact["record"]:
            if key in _REF_ENTITY:
                needed_entities.add(_REF_ENTITY[key][0])
    maps: Dict[str, Dict[str, str]] = {}
    for entity in needed_entities:
        rows = get_rows(entity, "id,source_id")
        maps[entity] = {r["source_id"]: r["id"] for r in rows if r.get("source_id") and r.get("id")}

    resolved: List[Dict[str, Any]] = []
    for fact in preview_facts:
        record = {k: v for k, v in fact["record"].items() if not k.endswith("_ref")}
        for key, value in fact["record"].items():
            if key not in _REF_ENTITY:
                continue
            entity, id_column = _REF_ENTITY[key]
            resolved_id = maps.get(entity, {}).get(value)
            if resolved_id is None:
                return [], (f"cannot resolve {key}={value!r} for a {fact['fact_table']} record; "
                            f"the referenced {entity} is not in the store yet")
            record[id_column] = resolved_id
        resolved.append({"fact_table": fact["fact_table"], "record": record,
                         "provenance": fact.get("provenance", {})})
    return resolved, None


def _call_apply(project_root: Path, batch_id: str, company_id: Optional[str], note: Optional[str],
                facts: List[Dict[str, Any]],
                rpc: Optional[Callable[[str, dict], Tuple[int, bytes]]] = None) -> Tuple[int, bytes]:
    body = {"p_batch_id": batch_id, "p_company_id": company_id, "p_note": note, "p_facts": facts}
    if rpc is not None:
        return rpc("apply_write_batch", body)
    return store_mod.authed_request(project_root, "POST", "/rest/v1/rpc/apply_write_batch", body)


# --------------------------------------------------------------------------- #
# retract
# --------------------------------------------------------------------------- #
def retract(project_root: Path, args,
            post: Optional[Callable[[str, dict], Tuple[int, bytes]]] = None) -> Result:
    result = Result("store retract")
    if not store_mod.UUID_RE.match(args.fact or ""):
        result.add_error("provide a valid --fact <uuid> (the database id of the fact to retract)")
        return result
    if not (args.reason or "").strip():
        result.add_error("provide a --reason for the retraction (it is recorded)")
        return result

    row = {"fact_table": args.fact_table, "fact_id": args.fact, "reason": args.reason}
    if post is not None:
        status, body = post("retraction", row)
    else:
        status, body = store_mod.authed_request(
            project_root, "POST", "/rest/v1/retraction", row)
    if status not in (200, 201, 204):
        result.add_error(f"the store refused the retraction (status {status}); only a staff or "
                         f"helper session may retract")
        result.summary = "Retraction refused."
        return result

    result.data = {"fact_table": args.fact_table, "fact_id": args.fact, "reason": args.reason}
    result.summary = (f"Retracted {args.fact_table} {args.fact}: {args.reason}. The original row is "
                      f"untouched; exports and briefs now exclude it.")
    return result


# --------------------------------------------------------------------------- #
# review (founder queue)
# --------------------------------------------------------------------------- #
def review(project_root: Path, args,
           rpc: Optional[Callable[[str, dict], Tuple[int, bytes]]] = None,
           patch: Optional[Callable[[str, dict], Tuple[int, bytes]]] = None) -> Result:
    result = Result("store review")
    if not store_mod.UUID_RE.match(args.submission or ""):
        result.add_error("provide a valid --submission <uuid>")
        return result
    if bool(args.accept) == bool(args.reject):
        result.add_error("choose exactly one of --accept or --reject")
        return result

    if args.reject:
        row = {"status": "rejected"}
        path = f"/rest/v1/submission?id=eq.{args.submission}"
        status, body = patch("submission", row) if patch else \
            store_mod.authed_request(project_root, "PATCH", path, row)
        if status not in (200, 204):
            result.add_error(f"could not reject the submission (status {status}); a staff or helper "
                             f"session is required")
            result.summary = "Reject refused."
            return result
        result.data = {"submission": args.submission, "status": "rejected"}
        result.summary = f"Rejected submission {args.submission}."
        return result

    body_in = {"p_submission_id": args.submission}
    status, body = rpc("accept_submission", body_in) if rpc else \
        store_mod.authed_request(project_root, "POST", "/rest/v1/rpc/accept_submission", body_in)
    if status not in (200, 201):
        result.add_error(f"the store refused to accept the submission (status {status}); a founder may "
                         f"auto-accept only their own metric submissions, and review classes need staff")
        result.summary = "Accept refused."
        return result
    payload = json.loads(body)
    result.data = {"submission": args.submission, "store_response": payload}
    result.summary = (f"Accepted submission {args.submission}: "
                      f"{(payload or {}).get('fact_count', 0)} fact(s) written with the founder as source.")
    return result


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _default_get_rows(project_root: Path) -> Callable[[str, str], List[Dict[str, Any]]]:
    def get_rows(table: str, select: str) -> List[Dict[str, Any]]:
        status, body = store_mod.authed_request(project_root, "GET", f"/rest/v1/{table}?select={select}")
        if status != 200:
            return []
        return json.loads(body)
    return get_rows


def _first(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, list):
        return value[0] if value else None
    return value
