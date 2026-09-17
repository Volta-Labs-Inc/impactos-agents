"""The founder shim: a deliberately tiny surface a founder uses to submit facts
about their own company and to check what they have submitted.

It exposes exactly two commands — ``submit`` and ``status`` — and nothing else.
It never writes a fact table (6a denies that to a founder); a submission lands as
``pending`` and only the guarded ``accept_submission`` function can turn it into
facts, and only per the acceptance rules. The shim signs in through the same
per-user session ``impactos store login`` creates; it never holds an
administrator key and never receives the repository's other commands.

Proposals travel in the submission's ``raw_payload_ref`` as JSON:

    {"fields": [{"field_class": "metric", "fact_table": "company_update",
                 "record": {"source_system": "founder", "source_id": "...",
                            "update_date": "2026-03-31", "current_ftes": 7}}]}
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import paths
from . import store as store_mod
from .result import Result


def _submitted_at() -> str:
    return datetime.date.today().isoformat()


def submit(project_root: Path, args) -> Result:
    result = Result("founder submit")
    if not store_mod.UUID_RE.match(args.company or ""):
        result.add_error("provide your company's --company <uuid>")
        return result

    fields_path = Path(args.fields) if args.fields else None
    if not fields_path or not fields_path.exists():
        result.add_error("provide --fields <path> to a JSON file: {\"fields\": [ ... ]}")
        return result
    try:
        payload = json.loads(fields_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result.add_error(f"--fields is not valid JSON: {exc}")
        return result
    fields = payload.get("fields") if isinstance(payload, dict) else payload
    if not isinstance(fields, list) or not fields:
        result.add_error("the fields file must contain a non-empty \"fields\" list")
        return result

    source_id = args.source_id or f"shim-{args.company[:8]}-{_submitted_at()}"
    row = {
        "source_system": "founder_shim",
        "source_id": source_id,
        "company_id": args.company,
        "channel": args.channel or "shim",
        "submitted_at": _submitted_at(),
        "status": "pending",
        "raw_payload_ref": json.dumps({"fields": fields}, sort_keys=True, ensure_ascii=False),
    }
    status, body = store_mod.authed_request(
        project_root, "POST", "/rest/v1/submission?select=id,status", row)
    if status not in (200, 201):
        result.add_error(f"the store refused the submission (status {status}); sign in with "
                         f"`impactos store login` as the founder of this company first")
        result.summary = "Submission refused."
        return result

    created = body and json.loads(body)
    submission_id = (created[0]["id"] if isinstance(created, list) and created else None)
    result.data = {"submission_id": submission_id, "status": "pending",
                   "field_count": len(fields), "company": args.company}
    result.summary = (f"Submitted {len(fields)} proposed field(s) for company {args.company}: "
                      f"pending review. A person accepts before anything is recorded.")
    return result


def status(project_root: Path, args) -> Result:
    result = Result("founder status")
    select = "id,source_id,status,channel,submitted_at,company_id"
    status_code, body = store_mod.authed_request(
        project_root, "GET", f"/rest/v1/submission?select={select}&order=submitted_at.desc")
    if status_code != 200:
        result.add_error(f"could not read your submissions (status {status_code}); sign in with "
                         f"`impactos store login` first")
        return result
    rows = json.loads(body)
    by_status: dict = {}
    for row in rows:
        by_status[row.get("status")] = by_status.get(row.get("status"), 0) + 1
    result.data = {"submissions": rows, "count": len(rows), "by_status": by_status}
    counts = ", ".join(f"{s}={n}" for s, n in sorted(by_status.items())) or "none"
    result.summary = f"{len(rows)} submission(s) you can see ({counts})."
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="impactos-founder",
        description="Founder shim: submit facts about your company, and check their status.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--json", action="store_true", help="emit the full result envelope as JSON")
        p.add_argument("--project-root", type=Path, default=Path.cwd(),
                       help="project directory that holds workspace/ (default: cwd)")

    sp = sub.add_parser("submit", help="submit proposed facts about your company (lands pending)")
    sp.add_argument("--company", required=True, help="your company's uuid")
    sp.add_argument("--fields", required=True, help="path to a JSON file: {\"fields\": [ ... ]}")
    sp.add_argument("--source-id", dest="source_id", help="a stable id for this submission")
    sp.add_argument("--channel", help="submission channel label (default: shim)")
    add_common(sp)
    sp.set_defaults(func=submit)

    tp = sub.add_parser("status", help="list the submissions you can see and their status")
    add_common(tp)
    tp.set_defaults(func=status)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    paths.inject_vendor()
    parser = build_parser()
    args = parser.parse_args(argv)
    result = args.func(args.project_root, args)
    return result.emit(as_json=getattr(args, "json", False))


if __name__ == "__main__":
    sys.exit(main())
