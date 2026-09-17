"""Argument parsing and command dispatch for the ``impactos`` CLI.

Every command supports ``--json`` and returns an exit code: 0 pass, 2 warnings,
1 fail. The tool makes no network or model calls and never writes to a source
file; all output lands under the git-ignored ``workspace/`` tree.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import interview, parsers, paths, workspace
from . import __version__
from .check import run_check
from .mapping import MappingError, apply_mapping, load_mapping
from .result import Result

HASH_SET = ["profile.json", "bai-v5.xlsx", "gaps.md", "provenance.json"]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

def cmd_preflight(args) -> Result:
    return workspace.preflight(args.project_root)


def cmd_init(args) -> Result:
    return workspace.init(args.project_root)


def cmd_state(args) -> Result:
    return workspace.state(args.project_root)


def cmd_check(args) -> Result:
    mode = "tracked" if args.tracked else "staged"
    return run_check(args.project_root, mode)


def cmd_parse(args) -> Result:
    result = Result("parse")
    source = Path(args.source)
    if not source.exists():
        result.add_error(f"source not found: {source}")
        return result

    source_type = args.type or parsers.detect_source_type(source)
    if source_type == "bai":
        payload, errors = parsers.parse_bai(source)
    elif source_type == "transcript":
        payload, errors = parsers.parse_transcript(source)
    else:
        payload, errors = parsers.parse_export(source)

    period = args.period or "unscoped"
    if args.out:
        out_path = Path(args.out)
    else:
        out_path = paths.workspace_dir(args.project_root) / "sources" / period / f"{source.stem}.source.json"
    _write_json(out_path, payload)

    summary_counts: Dict[str, Any] = {}
    if payload.get("source_type") == "transcript":
        summary_counts = {"segments": len(payload["transcript"].get("segments", []))}
    else:
        summary_counts = {name: len(s["rows"]) for name, s in payload.get("sheets", {}).items()}

    result.data = {
        "source_type": payload.get("source_type"),
        "vendor": payload.get("vendor"),
        "content_sha256": payload.get("meta", {}).get("content_sha256"),
        "payload_path": str(out_path),
        "counts": summary_counts,
        "structural_errors": errors,
    }
    for error in errors:
        result.add_warning(error)
    result.summary = f"Parsed {source.name} as {payload.get('vendor')} ({payload.get('source_type')}); wrote {out_path.name}."
    return result


def cmd_apply_mapping(args) -> Result:
    result = Result("apply-mapping")
    source = Path(args.source)
    mapping_path = Path(args.mapping)
    if not source.exists():
        result.add_error(f"source payload not found: {source}")
        return result
    if not mapping_path.exists():
        result.add_error(f"mapping not found: {mapping_path}")
        return result

    payload = json.loads(source.read_text(encoding="utf-8"))
    mapping = load_mapping(mapping_path)

    records_path = paths.workspace_dir(args.project_root) / "state" / args.period / "records.json"
    prior = None
    if records_path.exists():
        prior = json.loads(records_path.read_text(encoding="utf-8"))

    try:
        document = apply_mapping(
            payload, mapping, args.period, confirmed=args.confirmed, prior_records=prior
        )
    except MappingError as exc:
        result.add_error(str(exc))
        result.summary = "Refused."
        return result

    if args.out:
        records_path = Path(args.out)
    _write_json(records_path, document)

    record_counts = {dt: len(rows) for dt, rows in document["records"].items()}
    result.data = {
        "period": args.period,
        "records_path": str(records_path),
        "record_counts": record_counts,
        "additions": document.get("additions", []),
        "flags": document.get("flags", []),
    }
    for addition in document.get("additions", []):
        result.add_warning(f"source column not in mapping (added since it was written): {addition}")
    for flag in document.get("flags", []):
        if flag.get("flag") == "never_inferred_demographic":
            result.add_warning(
                f"{flag['data_type']} row {flag['row']}: demographic hint present but not declared; left unset"
            )
    result.summary = f"Applied mapping for {args.period}: " + ", ".join(
        f"{dt}={n}" for dt, n in sorted(record_counts.items())
    )
    return result


def cmd_export(args) -> Result:
    from .exporter import Exporter, ExportError

    result = Result("export")
    records_path = paths.workspace_dir(args.project_root) / "state" / args.period / "records.json"
    if not records_path.exists():
        result.add_error(f"no records for period {args.period!r}; run apply-mapping first")
        return result

    document = json.loads(records_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out) if args.out else paths.workspace_dir(args.project_root) / "reports" / args.period

    try:
        summary = Exporter(document).build(out_dir)
    except ExportError as exc:
        result.add_error(str(exc))
        result.summary = "Export refused."
        return result

    hash_set = {name: _sha256_file(out_dir / name) for name in HASH_SET}

    run_manifest = {
        "tool_version": __version__,
        "period": args.period,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sources": document.get("sources", []),
        "hash_set_sha256": hash_set,
        "template_problems": summary["template_problems"],
    }
    _write_json(out_dir / "run.json", run_manifest)

    result.data = {
        "period": args.period,
        "report_dir": str(out_dir),
        "hash_set": HASH_SET,
        "hash_set_sha256": hash_set,
        "populated_count": summary["populated_count"],
        "gap_count": summary["gap_count"],
        "provenance_cell_count": summary["provenance_cell_count"],
        "template_problems": summary["template_problems"],
        "run_json_excluded": True,
    }
    if summary["template_problems"]:
        for problem in summary["template_problems"]:
            result.add_error(f"output is not a valid BAI v5 template: {problem}")
    result.summary = (
        f"Exported {args.period}: {summary['populated_count']} profile fields populated, "
        f"{summary['gap_count']} gaps, {summary['provenance_cell_count']} provenance cells."
    )
    return result


def _default_questions_path() -> Path:
    return paths.REPO_ROOT / "skills" / "onboarding" / "questions.json"


def cmd_interview(args) -> Result:
    """Deterministic bookkeeping for the onboarding interview (SR-02, SR-05)."""
    result = Result("interview")
    state_path = paths.workspace_dir(args.project_root) / "state" / "interview.json"

    if args.action == "route":
        source_map_path = Path(args.source_map) if args.source_map else args.project_root / "source-map.json"
        if not source_map_path.exists():
            result.add_error(f"source map not found: {source_map_path}")
            return result
        source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
        rows = interview.routes_from_source_map(source_map)
        record = {"source_map": str(source_map_path), "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "routes": rows}
        _write_json(paths.workspace_dir(args.project_root) / "state" / "route.json", record)
        result.data = {"routes": rows, "route_path": str(paths.workspace_dir(args.project_root) / "state" / "route.json")}
        for row in rows:
            if not row["matches_recommendation"]:
                result.add_warning(
                    f"{row['data_type']}: chosen route {row['chosen_route']!r} differs from recommendation {row['recommendation']!r}"
                )
        result.summary = "Route recommendations: " + ", ".join(f"{r['data_type']}={r['recommendation']}" for r in rows)
        return result

    if args.action == "reset":
        if state_path.exists():
            state_path.unlink()
        result.data = {"reset": True, "state_path": str(state_path)}
        result.summary = "Interview state cleared."
        return result

    questions_path = Path(args.questions) if args.questions else _default_questions_path()
    if not questions_path.exists():
        result.add_error(f"questions file not found: {questions_path}")
        return result
    try:
        questions = interview.load_questions(questions_path)
        state = interview.load_state(state_path)
        if args.action == "answer":
            if not args.id:
                result.add_error("answer requires --id")
                return result
            interview.record_answer(state, args.id, args.value, questions)
            interview.save_state(state_path, state)
    except interview.InterviewError as exc:
        result.add_error(str(exc))
        return result

    nxt = interview.next_question(questions, state)
    result.data = {
        "action": args.action,
        "next_question": nxt,
        "answered": interview.answered_ids(questions, state),
        "remaining": interview.remaining_ids(questions, state),
        "complete": nxt is None,
        "state_path": str(state_path),
    }
    if nxt is None:
        result.summary = f"Interview complete: {len(questions)} questions answered."
    else:
        result.summary = f"Next question ({nxt['id']}): {nxt.get('prompt', '')}"
    return result


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="impactos", description=__doc__)
    parser.add_argument("--version", action="version", version=f"impactos {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--json", action="store_true", help="emit the full result envelope as JSON")
        p.add_argument(
            "--project-root", type=Path, default=Path.cwd(),
            help="project directory that contains workspace/ (default: cwd)",
        )

    p = sub.add_parser("preflight", help="report interpreter version and a writable workspace")
    add_common(p)
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("init", help="create the workspace tree, config and pre-commit hook")
    add_common(p)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("parse", help="normalise a source file into a source payload")
    p.add_argument("--source", required=True, help="path to the source file")
    p.add_argument("--type", choices=["bai", "export", "transcript"], help="source type (auto-detected if omitted)")
    p.add_argument("--period", help="reporting period label (e.g. 2026-06-30)")
    p.add_argument("--out", help="write the payload here instead of the workspace")
    add_common(p)
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("apply-mapping", help="apply a confirmed mapping to a source payload")
    p.add_argument("--source", required=True, help="path to a source payload (from `parse`)")
    p.add_argument("--mapping", required=True, help="path to the mapping JSON")
    p.add_argument("--period", required=True, help="reporting period label")
    p.add_argument("--confirmed", action="store_true", help="required: confirm the mapping is correct")
    p.add_argument("--out", help="write the records document here instead of the workspace")
    add_common(p)
    p.set_defaults(func=cmd_apply_mapping)

    p = sub.add_parser("export", help="build the BAI v5 workbook, profile, gaps and provenance")
    p.add_argument("--period", required=True, help="reporting period label")
    p.add_argument("--out", help="write the report set here instead of the workspace")
    add_common(p)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("check", help="scan staged (or tracked) files for secrets and PII")
    p.add_argument("--tracked", action="store_true", help="scan all tracked files (default: staged only)")
    add_common(p)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("state", help="print a JSON workspace summary for skills")
    add_common(p)
    p.set_defaults(func=cmd_state)

    p = sub.add_parser("interview", help="onboarding interview bookkeeping: next/answer/status/route/reset")
    p.add_argument("--action", choices=["next", "answer", "status", "route", "reset"], default="next",
                   help="next unanswered question (default), record an answer, status, route rule, or reset")
    p.add_argument("--id", help="question id (for --action answer)")
    p.add_argument("--value", help="answer value (for --action answer)")
    p.add_argument("--questions", help="path to questions.json (default: skills/onboarding/questions.json)")
    p.add_argument("--source-map", dest="source_map", help="path to source-map.json (for --action route)")
    add_common(p)
    p.set_defaults(func=cmd_interview)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    paths.inject_vendor()
    parser = build_parser()
    args = parser.parse_args(argv)
    result = args.func(args)
    return result.emit(as_json=getattr(args, "json", False))


if __name__ == "__main__":
    sys.exit(main())
