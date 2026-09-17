"""Apply a confirmed mapping to a source payload, producing contract records.

Guarantees enforced here:

* ``--confirmed`` is required; an unconfirmed run refuses.
* Every data type must declare an ``identity`` column; a mapping missing one for
  any data type refuses and names it.
* Columns removed or renamed since the mapping was written refuse and name them.
  Columns merely added since are listed and the mapping is still applied.
* Duplicate identities within one data type refuse.
* Demographic, company-type and funding fields are set only from source columns
  that declare them; a demographic hint in a name or free-text cell is never
  turned into a value — it is left unset and flagged for a person.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import contract, normalisers

# Pronoun / gender hints that must NEVER be turned into a demographic value.
_DEMOGRAPHIC_HINT = re.compile(
    r"\b(she|he|they)\s*/\s*(her|him|them)\b|\b(she/her|he/him|they/them)\b",
    re.IGNORECASE,
)


class MappingError(Exception):
    """A hard mapping failure (refusal)."""


def load_mapping(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sheet_for(mapping_dt: Dict[str, Any], payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    sheets = payload.get("sheets", {})
    sheet_name = mapping_dt.get("sheet", "default")
    if sheet_name not in sheets:
        raise MappingError(f"source has no sheet {sheet_name!r} (available: {sorted(sheets)})")
    return sheet_name, sheets[sheet_name]


def _referenced_columns(mapping_dt: Dict[str, Any]) -> List[str]:
    columns = list(mapping_dt.get("columns", {}).keys())
    if mapping_dt.get("identity"):
        columns.append(mapping_dt["identity"])
    columns.extend(mapping_dt.get("declared_demographics", {}).keys())
    return columns


def _apply_transform(value: Any, spec: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
    transform = spec.get("transform", "copy")
    if transform == "copy":
        return normalisers.normalize_str(value), None
    if transform == "date":
        return normalisers.normalize_date(value)
    if transform == "number":
        return normalisers.normalize_number(value)
    if transform == "yes_no":
        return normalisers.normalize_yes_no(value), None
    if transform == "split_name_first":
        return normalisers.split_name(value)[0], None
    if transform == "split_name_last":
        return normalisers.split_name(value)[1], None
    if transform == "money":
        amount, error = normalisers.normalize_number(value)
        currency = spec.get("currency", "CAD")
        if amount is None:
            return None, error
        return {"amount": amount, "currency": currency}, error
    if transform == "vocabulary":
        vocab = spec.get("vocabulary_values", [])
        return normalisers.normalize_vocabulary(value, vocab)
    raise MappingError(f"unknown transform {transform!r}")


def apply_mapping(
    payload: Dict[str, Any],
    mapping: Dict[str, Any],
    period: str,
    confirmed: bool,
    prior_records: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a records document. Raises :class:`MappingError` on a refusal."""
    if not confirmed:
        raise MappingError("apply-mapping refuses without --confirmed")

    data_types = mapping.get("data_types")
    if not data_types:
        raise MappingError("mapping declares no data_types")

    # Identity gate: every data type must declare an identity column.
    missing_identity = [name for name, spec in data_types.items() if not spec.get("identity")]
    if missing_identity:
        raise MappingError(
            "mapping is missing an identity column for: " + ", ".join(sorted(missing_identity))
        )

    # Column drift, per sheet. Referenced columns are the UNION across every data
    # type that reads that sheet. A referenced column absent from the source is a
    # removal/rename (refuse); a source column no data type references is an
    # addition (listed, mapping still applied).
    referenced_by_sheet: Dict[str, set] = {}
    sheet_columns_by_sheet: Dict[str, set] = {}
    for name, spec in data_types.items():
        sheet_name, sheet = _sheet_for(spec, payload)
        referenced_by_sheet.setdefault(sheet_name, set()).update(_referenced_columns(spec))
        sheet_columns_by_sheet[sheet_name] = set(sheet["columns"])

    removed: List[str] = []
    added: List[str] = []
    for sheet_name, referenced in referenced_by_sheet.items():
        sheet_columns = sheet_columns_by_sheet[sheet_name]
        for column in sorted(referenced - sheet_columns):
            removed.append(f"{sheet_name}:{column}")
        for column in sorted(sheet_columns - referenced):
            added.append(f"{sheet_name}:{column}")
    if removed:
        message = "source is missing mapped columns (removed or renamed): " + ", ".join(sorted(removed))
        if added:
            message += "; possibly renamed to: " + ", ".join(sorted(set(added)))
        message += " — re-confirm the mapping"
        raise MappingError(message)

    source_file = payload.get("meta", {}).get("source_file", "unknown")
    source_sha = payload.get("meta", {}).get("content_sha256", "")

    records: Dict[str, List[Dict[str, Any]]] = {}
    flags: List[Dict[str, Any]] = []
    duplicate_errors: List[str] = []

    for data_type, spec in data_types.items():
        sheet_name, sheet = _sheet_for(spec, payload)
        identity_col = spec["identity"]
        constants = spec.get("constants", {})
        columns = spec.get("columns", {})
        declared_demo = spec.get("declared_demographics", {})
        seen_identities: Dict[str, int] = {}
        built: List[Dict[str, Any]] = []

        for row_index, row in enumerate(sheet["rows"], start=2):
            identity_value = normalisers.normalize_str(row.get(identity_col))
            if identity_value is None:
                flags.append({
                    "data_type": data_type,
                    "row": row_index,
                    "flag": "missing_identity",
                    "detail": f"blank {identity_col!r}; row skipped",
                })
                continue
            if identity_value in seen_identities:
                duplicate_errors.append(
                    f"{data_type}: duplicate identity {identity_value!r} "
                    f"(rows {seen_identities[identity_value]} and {row_index})"
                )
                continue
            seen_identities[identity_value] = row_index

            fields: Dict[str, Any] = {}
            provenance: Dict[str, Any] = {}
            record_flags: List[str] = []

            # source_id defaults to the identity value (identity IS the source id),
            # so refs to this record line up without a redundant column mapping.
            if "source_id" in contract.data_type_fields(data_type):
                fields["source_id"] = identity_value
                provenance["source_id"] = {
                    "source_file": source_file,
                    "sha256": source_sha,
                    "sheet": sheet_name,
                    "column": identity_col,
                    "row_identity": identity_value,
                }

            for field, value in constants.items():
                fields[field] = value
                provenance[field] = {
                    "origin": "mapping_constant",
                    "value": value,
                    "mapping": mapping.get("source"),
                    "row_identity": identity_value,
                }

            for column, col_spec in columns.items():
                if col_spec.get("transform") == "funder_stage_to_rung":
                    continue  # handled in a dedicated pass below
                field = col_spec["field"]
                transformed, error = _apply_transform(row.get(column), col_spec)
                if error:
                    flags.append({
                        "data_type": data_type,
                        "row": row_index,
                        "identity": identity_value,
                        "flag": "unparseable_value",
                        "detail": f"{column}: {error}",
                    })
                fields[field] = transformed
                provenance[field] = {
                    "source_file": source_file,
                    "sha256": source_sha,
                    "sheet": sheet_name,
                    "column": column,
                    "row_identity": identity_value,
                }

            # funder_stage_to_rung: author-declared track constant + reported stage.
            for column, col_spec in columns.items():
                if col_spec.get("transform") != "funder_stage_to_rung":
                    continue
                reported = normalisers.normalize_str(row.get(column))
                track_slug = fields.get("track") or col_spec.get("track")
                if reported and track_slug:
                    rung = contract.lowest_rung_for_funder_stage(track_slug, reported)
                    if rung is None:
                        flags.append({
                            "data_type": data_type,
                            "row": row_index,
                            "identity": identity_value,
                            "flag": "unmapped_stage",
                            "detail": f"{reported!r} is not a funder stage on track {track_slug!r}",
                        })
                    else:
                        fields[col_spec["field"]] = rung
                        provenance[col_spec["field"]] = {
                            "source_file": source_file,
                            "sha256": source_sha,
                            "sheet": sheet_name,
                            "column": column,
                            "row_identity": identity_value,
                            "note": f"funder stage {reported!r} -> rung {rung} on declared track {track_slug!r}",
                        }

            # Declared demographics: only explicit yes cells become values.
            if declared_demo:
                groups: List[str] = []
                for column, group in declared_demo.items():
                    if normalisers.normalize_yes_no(row.get(column)) is True:
                        groups.append(group)
                if groups:
                    fields["demographics"] = groups
                    provenance["demographics"] = {
                        "source_file": source_file,
                        "sha256": source_sha,
                        "sheet": sheet_name,
                        "column": ",".join(sorted(declared_demo.keys())),
                        "row_identity": identity_value,
                    }

            # Never-infer: a demographic hint with no declared demographic column
            # is flagged, never converted into a value.
            if not declared_demo:
                hint_source = " ".join(
                    str(row.get(col) or "")
                    for col in columns
                    if contract.field_classification(data_type, columns[col]["field"]) in ("personal", "descriptive")
                )
                if _DEMOGRAPHIC_HINT.search(hint_source):
                    record_flags.append("never_inferred_demographic")
                    flags.append({
                        "data_type": data_type,
                        "row": row_index,
                        "identity": identity_value,
                        "flag": "never_inferred_demographic",
                        "detail": "a demographic hint was present but no source column "
                                  "declares demographics; demographics left unset",
                    })

            built.append({
                "identity": identity_value,
                "fields": fields,
                "provenance": provenance,
                "flags": record_flags,
            })

        records[data_type] = built

    if duplicate_errors:
        raise MappingError("; ".join(duplicate_errors))

    document = _merge(prior_records, {
        "period": period,
        "records": records,
    })
    document.setdefault("sources", [])
    source_entry = {"source_file": source_file, "content_sha256": source_sha, "mapping": mapping.get("source")}
    if source_entry not in document["sources"]:
        document["sources"].append(source_entry)
    document["flags"] = (prior_records or {}).get("flags", []) + flags if prior_records else flags
    document["additions"] = sorted(set((prior_records or {}).get("additions", []) + added))
    return document


def _merge(prior: Optional[Dict[str, Any]], new: Dict[str, Any]) -> Dict[str, Any]:
    """Merge new records into a prior period document by (data_type, identity)."""
    if not prior:
        return {"period": new["period"], "records": new["records"]}
    merged_records: Dict[str, List[Dict[str, Any]]] = {
        dt: list(rows) for dt, rows in prior.get("records", {}).items()
    }
    for data_type, rows in new["records"].items():
        existing = {r["identity"]: i for i, r in enumerate(merged_records.get(data_type, []))}
        bucket = merged_records.setdefault(data_type, [])
        for row in rows:
            if row["identity"] in existing:
                bucket[existing[row["identity"]]] = row
            else:
                existing[row["identity"]] = len(bucket)
                bucket.append(row)
    return {"period": new["period"], "records": merged_records}
