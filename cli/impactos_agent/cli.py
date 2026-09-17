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
import os
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


# --- store subcommands: login/provision/access (6a); write/retract/review/export (6b) --- #
def cmd_store(args) -> Result:
    from . import store as store_mod

    if args.store_command == "login":
        return store_mod.login(args.project_root, args)
    if args.store_command == "provision":
        return store_mod.provision(args.project_root, args, sys.argv[1:], dict(os.environ))
    if args.store_command == "access" and args.access_command == "end":
        return store_mod.access_end(args.project_root, args)
    if args.store_command == "access" and args.access_command == "check":
        return store_mod.access_check(args.project_root, args)
    if args.store_command == "write":
        from . import store_writes
        return store_writes.write(args.project_root, args)
    if args.store_command == "retract":
        from . import store_writes
        return store_writes.retract(args.project_root, args)
    if args.store_command == "review":
        from . import store_writes
        return store_writes.review(args.project_root, args)
    if args.store_command == "export":
        return cmd_store_export(args)
    result = Result("store")
    result.add_error("unknown store command")
    return result


def cmd_store_export(args) -> Result:
    """Build the export set from the store (child 6b), excluding retracted facts.

    The store reader rebuilds the same records shape the file route produces, so
    the exporter and its provenance run unchanged over it.
    """
    from . import store_reader
    from .exporter import Exporter, ExportError

    result = Result("store export")
    period = args.period or "store"
    try:
        document = store_reader.read_records(args.project_root, period)
    except store_reader.StoreReadError as exc:
        result.add_error(str(exc))
        result.summary = "Export refused."
        return result

    out_dir = Path(args.out) if args.out else paths.workspace_dir(args.project_root) / "reports" / period
    try:
        summary = Exporter(document).build(out_dir)
    except ExportError as exc:
        result.add_error(str(exc))
        result.summary = "Export refused."
        return result

    hash_set = {name: _sha256_file(out_dir / name) for name in HASH_SET}
    run_manifest = {
        "tool_version": __version__,
        "period": period,
        "route": "store",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "hash_set_sha256": hash_set,
        "template_problems": summary["template_problems"],
    }
    _write_json(out_dir / "run.json", run_manifest)

    result.data = {
        "period": period,
        "route": "store",
        "report_dir": str(out_dir),
        "hash_set": HASH_SET,
        "hash_set_sha256": hash_set,
        "populated_count": summary["populated_count"],
        "gap_count": summary["gap_count"],
        "provenance_cell_count": summary["provenance_cell_count"],
        "template_problems": summary["template_problems"],
    }
    if summary["template_problems"]:
        for problem in summary["template_problems"]:
            result.add_error(f"output is not a valid BAI v5 template: {problem}")
    result.summary = (
        f"Exported {period} from the store: {summary['populated_count']} profile fields populated, "
        f"{summary['gap_count']} gaps, {summary['provenance_cell_count']} provenance cells."
    )
    return result


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

    # Optional gate: refuse unless an acknowledged, still-valid compare exists.
    if getattr(args, "after_compare", None) is not None:
        gate_error = _compare_gate_error(args, document, out_dir)
        if gate_error:
            result.add_error(gate_error)
            result.summary = "Export refused."
            return result

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


def cmd_brief(args) -> Result:
    """Build a company or portfolio brief (A2UI blueprint + Markdown).

    Display-only: reads the file-route records for a period and never writes back
    into the record. Refuses to write an invalid blueprint.
    """
    from . import a2ui, brief

    result = Result("brief")
    if bool(args.company) == bool(args.portfolio):
        result.add_error("choose exactly one of --company <id> or --portfolio")
        return result

    # Resolve the records document. --from store reads the store (excluding
    # retracted facts) instead of a file-route records.json.
    if getattr(args, "from_route", "file") == "store":
        from . import store_reader
        try:
            document = store_reader.read_records(args.project_root, args.period or "store")
        except store_reader.StoreReadError as exc:
            result.add_error(str(exc))
            result.summary = "Refused."
            return result
        return _finish_brief(args, document, "store")

    # Resolve the records document.
    if args.records:
        records_path = Path(args.records)
    else:
        state_dir = paths.workspace_dir(args.project_root) / "state"
        if args.period:
            records_path = state_dir / args.period / "records.json"
        else:
            periods = sorted(
                (p.name for p in state_dir.iterdir() if p.is_dir() and (p / "records.json").exists()),
                reverse=True,
            ) if state_dir.exists() else []
            if not periods:
                result.add_error("no records found; run apply-mapping or pass --records / --period")
                return result
            records_path = state_dir / periods[0] / "records.json"
    if not records_path.exists():
        result.add_error(f"records not found: {records_path}")
        return result

    document = json.loads(records_path.read_text(encoding="utf-8"))
    return _finish_brief(args, document, str(records_path))


def _finish_brief(args, document, source_label: str) -> Result:
    """Build, validate and write a brief from a resolved records document."""
    from . import a2ui, brief

    result = Result("brief")
    try:
        built = brief.build_company_brief(document, args.company) if args.company \
            else brief.build_portfolio_brief(document)
    except brief.BriefError as exc:
        result.add_error(str(exc))
        result.summary = "Refused."
        return result

    schema_errors = a2ui.validate_messages(built["messages"])
    if schema_errors:
        for message in schema_errors:
            result.add_error(f"invalid A2UI blueprint: {message}")
        result.summary = "Refusing to write an invalid blueprint."
        return result

    out_dir = Path(args.out) if args.out else paths.workspace_dir(args.project_root) / "briefs"
    json_path = out_dir / f"{built['name']}.json"
    md_path = out_dir / f"{built['name']}.md"
    _write_json(json_path, built["messages"])
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(built["markdown"], encoding="utf-8")

    result.data = {
        "kind": "company" if args.company else "portfolio",
        "surface_id": built["surface_id"],
        "records_path": source_label,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "message_count": len(built["messages"]),
    }
    result.summary = f"Wrote {json_path.name} and {md_path.name} from {source_label}."
    return result


def _compare_gate_error(args, document, out_dir: Path) -> Optional[str]:
    """Return a refusal reason for ``export --after-compare``, or ``None`` to allow."""
    from . import compare as compare_mod

    compare_file = out_dir / "compare.json"
    if not compare_file.exists():
        return (
            f"no compare exists for period {args.period!r}; "
            f"run `impactos compare --period {args.period}` first"
        )
    comparison = json.loads(compare_file.read_text(encoding="utf-8"))
    ack = comparison.get("acknowledgement", {})

    if args.after_compare != ack.get("hash"):
        return "acknowledgement hash does not match the recorded compare; re-run compare and pass its hash"

    if compare_mod.sha256_of(document) != ack.get("current_records_sha256"):
        return "a source changed after compare (records differ); re-run compare before export"

    baseline_period = ack.get("baseline_period")
    baseline_sha = None
    if baseline_period is not None:
        baseline_file = compare_mod.baseline_path(args.project_root, baseline_period)
        if not baseline_file.exists():
            return "the prior baseline is missing; re-run compare before export"
        baseline_sha = compare_mod.sha256_of(json.loads(baseline_file.read_text(encoding="utf-8")))
    if baseline_sha != ack.get("baseline_sha256"):
        return "the prior baseline changed after compare; re-run compare before export"

    return None


def cmd_compare(args) -> Result:
    from . import compare as compare_mod

    result = Result("compare")
    records_file = compare_mod.records_path(args.project_root, args.period)
    if not records_file.exists():
        result.add_error(f"no records for period {args.period!r}; run apply-mapping first")
        result.summary = "Compare refused."
        return result

    records_doc = json.loads(records_file.read_text(encoding="utf-8"))

    prior_period = compare_mod.select_prior_period(args.project_root, args.period)
    prior_baseline = None
    if prior_period is not None:
        prior_baseline = json.loads(
            compare_mod.baseline_path(args.project_root, prior_period).read_text(encoding="utf-8")
        )

    comparison = compare_mod.compute(records_doc, prior_baseline)
    comparison["acknowledgement"] = compare_mod.acknowledgement(records_doc, prior_baseline)

    out_dir = Path(args.out) if args.out else paths.workspace_dir(args.project_root) / "reports" / args.period
    _write_json(out_dir / "compare.json", comparison)
    (out_dir / "compare.md").write_text(compare_mod.render_markdown(comparison), encoding="utf-8")

    # Refresh THIS period's own baseline for a future period to compare against.
    # Prior selection excludes the current label, so this never self-compares.
    _write_json(
        compare_mod.baseline_path(args.project_root, args.period),
        compare_mod.build_baseline(records_doc),
    )

    totals = {kind: 0 for kind in ("changed", "new", "absent", "unmatched", "missing_required")}
    for summary in comparison["data_types"].values():
        for kind in totals:
            totals[kind] += len(summary[kind])

    result.data = {
        "period": args.period,
        "baseline_period": prior_period,
        "compare_json": str(out_dir / "compare.json"),
        "compare_md": str(out_dir / "compare.md"),
        "acknowledgement_hash": comparison["acknowledgement"]["hash"],
        "totals": totals,
        "cost_of_support_present": comparison["cost_of_support_present"],
    }
    for data_type, summary in sorted(comparison["data_types"].items()):
        for entry in summary["unmatched"]:
            result.add_warning(
                f"{data_type} {entry['identity']} unmatched: reuses the name of "
                f"{entry['matches_existing_identity']} (never merged)"
            )
        for entry in summary["missing_required"]:
            result.add_warning(
                f"{data_type} {entry['identity']} missing required: {', '.join(entry['fields'])}"
            )
    result.summary = (
        f"Compared {args.period} to {prior_period or '(no prior period)'}: "
        f"{totals['changed']} changed, {totals['new']} new, {totals['absent']} absent, "
        f"{totals['unmatched']} unmatched, {totals['missing_required']} missing required. "
        f"Ack hash {comparison['acknowledgement']['hash'][:12]}."
    )
    return result


def cmd_access_grant(args) -> Result:
    from . import access

    result = Result("access grant")
    if args.scope not in access.SCOPES:
        result.add_error(f"--scope is required and must be one of: {', '.join(access.SCOPES)}")
        result.summary = "Refused."
        return result
    missing = [n for n, v in (("--name", args.name), ("--email", args.email), ("--start", args.start)) if not v]
    if missing:
        result.add_error("grant requires " + ", ".join(missing))
        result.summary = "Refused."
        return result

    data = access.load(args.project_root)
    entry = access.grant_entry(args.name, args.email, args.scope, args.start)
    data["grants"].append(entry)
    access.save(args.project_root, data)

    result.data = {"grant": entry, "count": len(data["grants"])}
    result.summary = f"Granted {args.scope} access to {args.name} ({args.email}) from {args.start}."
    return result


def cmd_access_end(args) -> Result:
    from . import access

    result = Result("access end")
    missing = [
        name for name, value in (
            ("--deletion-confirmed-by", args.deletion_confirmed_by),
            ("--confirmed-at", args.confirmed_at),
            ("--confirmation-text", args.confirmation_text),
        ) if not value
    ]
    if missing:
        result.add_error("ending access requires written deletion confirmation: " + ", ".join(missing))
        result.summary = "Refused."
        return result
    if not args.name:
        result.add_error("access end requires --name")
        result.summary = "Refused."
        return result

    data = access.load(args.project_root)
    ok, message, entry = access.end_grant(
        data, args.name, args.deletion_confirmed_by, args.confirmed_at, args.confirmation_text
    )
    if not ok:
        result.add_error(message)
        result.summary = "Refused."
        return result

    access.save(args.project_root, data)
    result.data = {"grant": entry}
    result.summary = (
        f"Ended access for {args.name}; deletion confirmed by {args.deletion_confirmed_by} "
        f"at {args.confirmed_at}."
    )
    return result


def cmd_access_list(args) -> Result:
    from . import access

    result = Result("access list")
    data = access.load(args.project_root)
    result.data = {"grants": data["grants"], "count": len(data["grants"])}
    result.summary = f"{len(data['grants'])} access record(s)."
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
    p.add_argument(
        "--after-compare",
        help="acknowledged compare hash; gates export on a still-valid compare for this period",
    )
    add_common(p)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("check", help="scan staged (or tracked) files for secrets and PII")
    p.add_argument("--tracked", action="store_true", help="scan all tracked files (default: staged only)")
    add_common(p)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("state", help="print a JSON workspace summary for skills")
    add_common(p)
    p.set_defaults(func=cmd_state)

    # --- store: per-user login, provisioning, access wrappers (issue #7 / 6a) - #
    store_p = sub.add_parser("store", help="the optional store: login, provisioning, access")
    store_sub = store_p.add_subparsers(dest="store_command", required=True)

    sp = store_sub.add_parser("login", help="sign in as a per-user session (Supabase Auth)")
    sp.add_argument("--email", help="account email")
    sp.add_argument("--password", help="password grant (fixture use)")
    sp.add_argument("--otp-request", action="store_true", help="send an email login code (real use)")
    sp.add_argument("--token", help="verify an email login code (real use)")
    sp.add_argument("--api-url", help="project API URL (defaults to the provisioned value)")
    sp.add_argument("--publishable-key", help="project publishable key (public; not a secret)")
    add_common(sp)
    sp.set_defaults(func=cmd_store)

    sp = store_sub.add_parser("provision", help="apply migrations via the management API")
    sp.add_argument("--project-ref", help="Supabase project reference")
    sp.add_argument("--api-url", help="override the project API URL")
    add_common(sp)
    sp.set_defaults(func=cmd_store)

    sp = store_sub.add_parser("access", help="access wrappers (end a role, check company access)")
    access_sub = sp.add_subparsers(dest="access_command", required=True)
    ap = access_sub.add_parser("end", help="end a user's role (e.g. a helper) by setting ends_at")
    ap.add_argument("--user", required=True, help="the user's UUID")
    ap.add_argument("--role", default="helper", help="role name to end (default: helper)")
    ap.add_argument("--at", help="timestamp to set (default: now)")
    add_common(ap)
    ap.set_defaults(func=cmd_store, store_command="access")
    cp = access_sub.add_parser("check", help="explicit access answer for a company (SR-21)")
    cp.add_argument("--company", required=True, help="the company UUID")
    add_common(cp)
    cp.set_defaults(func=cmd_store, store_command="access")

    # --- store writes (issue #8 / 6b): preview-confirm, retract, review, export - #
    wp = store_sub.add_parser("write", help="preview facts to write (or --confirm <hash> to apply)")
    wp.add_argument("--records", help="path to a records.json to write (from apply-mapping)")
    wp.add_argument("--period", help="period label to resolve records from the workspace")
    wp.add_argument("--confirm", help="apply the preview with this request hash")
    wp.add_argument("--note", help="an optional note recorded on the write batch")
    add_common(wp)
    wp.set_defaults(func=cmd_store)

    rp = store_sub.add_parser("retract", help="retract a fact by id (staff/helper); original untouched")
    rp.add_argument("--fact", required=True, help="the database id (uuid) of the fact to retract")
    rp.add_argument("--fact-table", dest="fact_table", required=True,
                    help="the fact's table (e.g. company_update, funding_event)")
    rp.add_argument("--reason", required=True, help="why the fact is retracted (recorded)")
    add_common(rp)
    rp.set_defaults(func=cmd_store)

    vp = store_sub.add_parser("review", help="accept or reject a founder submission (staff/helper)")
    vp.add_argument("--submission", required=True, help="the submission uuid")
    vp.add_argument("--accept", action="store_true", help="accept via the guarded acceptance function")
    vp.add_argument("--reject", action="store_true", help="reject the submission")
    add_common(vp)
    vp.set_defaults(func=cmd_store)

    ep = store_sub.add_parser("export", help="build the BAI export from the store (excludes retracted facts)")
    ep.add_argument("--period", help="period label for the report directory (default: 'store')")
    ep.add_argument("--out", help="write the report set here instead of the workspace")
    add_common(ep)
    ep.set_defaults(func=cmd_store)

    p = sub.add_parser("brief", help="build a company or portfolio brief (A2UI blueprint + Markdown)")
    p.add_argument("--company", help="company id (record identity) for a single-company brief")
    p.add_argument("--portfolio", action="store_true", help="build the portfolio brief instead")
    p.add_argument("--records", help="path to a records.json (default: resolve from the workspace)")
    p.add_argument("--period", help="reporting period label to read records for (default: latest)")
    p.add_argument("--from", dest="from_route", choices=["file", "store"], default="file",
                   help="read records from the file route (default) or the store")
    p.add_argument("--out", help="write the brief files here instead of workspace/briefs/")
    add_common(p)
    p.set_defaults(func=cmd_brief)
    # Issue #5: period comparison (identity-only) against the prior baseline.
    p = sub.add_parser("compare", help="compare a period to the prior period (identity-only matching)")
    p.add_argument("--period", required=True, help="reporting period label")
    p.add_argument("--out", help="write compare.json/compare.md here instead of the workspace")
    add_common(p)
    p.set_defaults(func=cmd_compare)

    # Issue #5: the file-route helper access record.
    p = sub.add_parser("access", help="record who may reach the workspace (file-route access)")
    access_sub = p.add_subparsers(dest="access_command", required=True)

    g = access_sub.add_parser("grant", help="record a person's access (name, email, scope, start)")
    g.add_argument("--name", help="the person's name")
    g.add_argument("--email", help="the person's email")
    g.add_argument("--scope", help="access scope: staff or helper")
    g.add_argument("--start", help="access start date (e.g. 2026-06-01)")
    add_common(g)
    g.set_defaults(func=cmd_access_grant)

    e = access_sub.add_parser("end", help="end access with written deletion confirmation")
    e.add_argument("--name", help="the person's name")
    e.add_argument("--deletion-confirmed-by", help="who confirmed the workspace copy was deleted")
    e.add_argument("--confirmed-at", help="when it was confirmed (e.g. 2026-09-16)")
    e.add_argument("--confirmation-text", help="the exact written confirmation")
    add_common(e)
    e.set_defaults(func=cmd_access_end)

    lst = access_sub.add_parser("list", help="list the access records")
    add_common(lst)
    lst.set_defaults(func=cmd_access_list)
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
