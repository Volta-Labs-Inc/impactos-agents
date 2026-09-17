"""The file-route helper access record (SR-13).

Who may reach the workspace is recorded in the git-ignored ``workspace/access.json``.
A grant records a person's name, email, scope (``staff`` or ``helper``) and start
date. Ending access records the written deletion confirmation -- who confirmed the
copy was deleted, when, and the exact confirmation text -- and is refused without
it. This is the file-route control VOL-250 names; nothing here reaches a source
system.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import paths

SCOPES = ("staff", "helper")
VERSION = "1.0.0"


def access_path(project_root: Path) -> Path:
    return paths.workspace_dir(project_root) / "access.json"


def load(project_root: Path) -> Dict[str, Any]:
    path = access_path(project_root)
    if not path.exists():
        return {"access_records_version": VERSION, "grants": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if "grants" not in data:
        # Migrate the local-only stub `init` writes, preserving its note.
        migrated: Dict[str, Any] = {"access_records_version": VERSION, "grants": []}
        if data.get("note"):
            migrated["note"] = data["note"]
        return migrated
    return data


def save(project_root: Path, data: Dict[str, Any]) -> None:
    path = access_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def grant_entry(name: str, email: str, scope: str, start: str) -> Dict[str, Any]:
    return {
        "name": name,
        "email": email,
        "scope": scope,
        "start": start,
        "status": "active",
        "end": None,
        "deletion_confirmation": None,
    }


def end_grant(
    data: Dict[str, Any],
    name: str,
    confirmed_by: str,
    confirmed_at: str,
    confirmation_text: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """End the active grant for ``name``. Returns ``(ok, message, entry)``."""
    for entry in data["grants"]:
        if entry["name"] == name and entry.get("status") == "active":
            entry["status"] = "ended"
            entry["end"] = confirmed_at
            entry["deletion_confirmation"] = {
                "confirmed_by": confirmed_by,
                "confirmed_at": confirmed_at,
                "confirmation_text": confirmation_text,
            }
            return True, "ended", entry
    return False, f"no active access record for {name!r}", None
