"""Deterministic period comparison against a prior-period baseline (SR-10).

`compare` matches the current period's records to the prior period ONLY on the
mapping's declared identity column -- the value stored on every record as
``identity`` when a mapping was applied. Per data type it reports:

* ``changed``          -- matched by identity, with one or more field differences
* ``new``              -- an unseen identity with no name collision
* ``absent``           -- an identity present in the prior period but not now
* ``unmatched``        -- an unseen identity whose name matches an existing record;
                          a name match NEVER authorises a merge, so the row is
                          flagged and proposed as new, never merged
* ``missing_required`` -- required contract fields left unset on a current record

Nothing here is probabilistic or fuzzy. Matching is exact on the identity value;
a name collision is an exact match on a name field. The whole comparison is a pure
function of its inputs, so an independent re-run reproduces it byte for byte.

The prior baseline for a period lives at ``workspace/state/periods/<period>.json``
(records plus a per-data-type identity index). Selecting the prior period as the
latest baseline whose label sorts before the current one means re-running the same
period never compares it to itself.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import contract, paths

# Priority order for a record's human-facing "name", used only to detect a name
# collision (an unseen identity that reuses an existing record's name). A data type
# with none of these fields simply has no name-collision detection, and every
# unseen identity is reported as ``new``.
NAME_FIELDS = ["legal_name", "name", "full_name", "title", "cohort_name", "label"]

NAME_MATCH_REASON = (
    "New identifier whose name matches an existing record; "
    "a name match never authorises a merge."
)


# --------------------------------------------------------------------------- #
# Locations
# --------------------------------------------------------------------------- #

def baselines_dir(project_root: Path) -> Path:
    return paths.workspace_dir(project_root) / "state" / "periods"


def baseline_path(project_root: Path, period: str) -> Path:
    return baselines_dir(project_root) / f"{period}.json"


def records_path(project_root: Path, period: str) -> Path:
    return paths.workspace_dir(project_root) / "state" / period / "records.json"


def select_prior_period(project_root: Path, current_period: str) -> Optional[str]:
    """The latest baseline period sorting strictly before ``current_period``.

    Excluding the current label is what makes a same-period re-run never compare a
    period to itself.
    """
    directory = baselines_dir(project_root)
    if not directory.exists():
        return None
    earlier = sorted(p.stem for p in directory.glob("*.json") if p.stem < current_period)
    return earlier[-1] if earlier else None


# --------------------------------------------------------------------------- #
# Hashing (used for the acknowledgement over the compared inputs)
# --------------------------------------------------------------------------- #

def _canonical(value: Any) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")


def sha256_of(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


# --------------------------------------------------------------------------- #
# Baseline
# --------------------------------------------------------------------------- #

def name_of(record: Dict[str, Any]) -> Optional[str]:
    fields = record.get("fields", {})
    for key in NAME_FIELDS:
        value = fields.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def build_baseline(records_doc: Dict[str, Any]) -> Dict[str, Any]:
    """A baseline is the period's records plus a per-data-type identity index."""
    records = records_doc.get("records", {})
    index: Dict[str, Dict[str, Optional[str]]] = {}
    for data_type, rows in records.items():
        index[data_type] = {row["identity"]: name_of(row) for row in rows}
    return {
        "period": records_doc.get("period"),
        "records": records,
        "identity_index": index,
    }


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #

def _required_fields(data_type: str) -> List[str]:
    try:
        fields = contract.data_type_fields(data_type)
    except KeyError:
        return []
    return sorted(name for name, spec in fields.items() if spec.get("required"))


def _diff_fields(prior: Dict[str, Any], current: Dict[str, Any]) -> List[Dict[str, Any]]:
    prior_fields = prior.get("fields", {})
    current_fields = current.get("fields", {})
    changes: List[Dict[str, Any]] = []
    for key in sorted(set(prior_fields) | set(current_fields)):
        before = prior_fields.get(key)
        after = current_fields.get(key)
        if before != after:
            changes.append({"field": key, "from": before, "to": after})
    return changes


def compare_data_type(
    data_type: str,
    prior_rows: List[Dict[str, Any]],
    current_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    prior_by_id = {row["identity"]: row for row in prior_rows}
    # First-seen wins so the collision target is deterministic.
    prior_name_to_id: Dict[str, Any] = {}
    for row in prior_rows:
        name = name_of(row)
        if name is not None:
            prior_name_to_id.setdefault(name, row["identity"])

    required = _required_fields(data_type)

    changed: List[Dict[str, Any]] = []
    new: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    missing_required: List[Dict[str, Any]] = []
    matched = 0
    current_ids = set()

    for record in current_rows:
        identity = record.get("identity")
        current_ids.add(identity)
        name = name_of(record)

        missing = [f for f in required if record.get("fields", {}).get(f) in (None, "")]
        if missing:
            missing_required.append({"identity": identity, "fields": missing})

        if identity in prior_by_id:
            matched += 1
            diffs = _diff_fields(prior_by_id[identity], record)
            if diffs:
                changed.append({"identity": identity, "name": name, "changes": diffs})
        elif name is not None and name in prior_name_to_id and prior_name_to_id[name] != identity:
            unmatched.append({
                "identity": identity,
                "name": name,
                "matches_existing_identity": prior_name_to_id[name],
                "resolution": "unmatched",
                "reason": NAME_MATCH_REASON,
            })
        else:
            new.append({"identity": identity, "name": name})

    absent = [
        {"identity": row["identity"], "name": name_of(row)}
        for row in prior_rows
        if row["identity"] not in current_ids
    ]

    key = lambda item: str(item["identity"])
    return {
        "matched": matched,
        "changed": sorted(changed, key=key),
        "new": sorted(new, key=key),
        "absent": sorted(absent, key=key),
        "unmatched": sorted(unmatched, key=key),
        "missing_required": sorted(missing_required, key=key),
    }


def _cost_of_support_present(records: Dict[str, List[Dict[str, Any]]]) -> bool:
    """The data contract omits cost of support by design (D-05); it is derivable
    only. This reports whether any mapped update nonetheless carries a value."""
    for update in records.get("company_update", []):
        if update.get("fields", {}).get("cost_of_support") not in (None, ""):
            return True
    return False


def compute(records_doc: Dict[str, Any], prior_baseline: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    current = records_doc.get("records", {})
    prior = (prior_baseline or {}).get("records", {})
    per_type: Dict[str, Any] = {}
    for data_type in sorted(set(current) | set(prior)):
        per_type[data_type] = compare_data_type(
            data_type, prior.get(data_type, []), current.get(data_type, [])
        )
    return {
        "period": records_doc.get("period"),
        "baseline_period": (prior_baseline or {}).get("period"),
        "data_types": per_type,
        "cost_of_support_present": _cost_of_support_present(current),
    }


def acknowledgement(records_doc: Dict[str, Any], prior_baseline: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """A hash over the compared inputs: the current records and the prior baseline.

    Export uses it to refuse when a source changed after the compare (the records
    differ) or when the prior baseline changed.
    """
    current_sha = sha256_of(records_doc)
    baseline_sha = sha256_of(prior_baseline) if prior_baseline is not None else None
    period = records_doc.get("period")
    baseline_period = (prior_baseline or {}).get("period")
    material = json.dumps(
        {
            "period": period,
            "baseline_period": baseline_period,
            "current_records_sha256": current_sha,
            "baseline_sha256": baseline_sha,
        },
        sort_keys=True,
    ).encode("utf-8")
    return {
        "hash": hashlib.sha256(material).hexdigest(),
        "period": period,
        "baseline_period": baseline_period,
        "current_records_sha256": current_sha,
        "baseline_sha256": baseline_sha,
    }


# --------------------------------------------------------------------------- #
# Markdown summary
# --------------------------------------------------------------------------- #

def _rows(entries: List[Dict[str, Any]], render) -> List[str]:
    return [f"  - {render(e)}" for e in entries] or ["  - (none)"]


def render_markdown(comparison: Dict[str, Any]) -> str:
    lines: List[str] = [
        f"# Period comparison -- {comparison['period']}",
        "",
        f"Prior period: {comparison['baseline_period'] or '(none -- first period)'}",
        f"Cost of support present: {'yes' if comparison['cost_of_support_present'] else 'no'}",
        "",
        "| Data type | Matched | Changed | New | Absent | Unmatched | Missing required |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for data_type in sorted(comparison["data_types"]):
        summary = comparison["data_types"][data_type]
        lines.append(
            f"| {data_type} | {summary['matched']} | {len(summary['changed'])} | "
            f"{len(summary['new'])} | {len(summary['absent'])} | {len(summary['unmatched'])} | "
            f"{len(summary['missing_required'])} |"
        )
    lines.append("")

    for data_type in sorted(comparison["data_types"]):
        summary = comparison["data_types"][data_type]
        if not (summary["unmatched"] or summary["missing_required"]):
            continue
        lines.append(f"## {data_type} -- rows needing a person")
        if summary["unmatched"]:
            lines.append("- Unmatched (a name match never authorises a merge):")
            lines.extend(
                _rows(
                    summary["unmatched"],
                    lambda e: f"{e['identity']} ({e.get('name')}) reuses the name of {e['matches_existing_identity']}",
                )
            )
        if summary["missing_required"]:
            lines.append("- Missing required fields:")
            lines.extend(
                _rows(summary["missing_required"], lambda e: f"{e['identity']}: {', '.join(e['fields'])}")
            )
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
