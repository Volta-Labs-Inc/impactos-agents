"""Build a company or portfolio brief as A2UI messages and Markdown.

Reads a period's contract records (the file-route ``records.json`` produced by
``apply-mapping``) and renders a display-only brief. A brief never writes back
into the record.

For a company it shows the profile, the track position and target, the last
three interactions, and any open flags. For the portfolio it shows one row per
company. Both are produced as two things at once from the same data:

* an A2UI v0.9.1 blueprint (``createSurface`` + ``updateComponents`` +
  ``updateDataModel``) using only the eight catalogue components, for the static
  renderer; and
* an equivalent Markdown document for harnesses without a browser.

The build is deterministic: identical records produce identical output, with no
embedded timestamps, so the Markdown golden and the blueprint are stable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import contract
from .a2ui import CATALOG_ID, PROTOCOL_VERSION

COMPANY_SURFACE = "brief"
PORTFOLIO_SURFACE = "portfolio"

# Ordered profile fields shown when present. Order is fixed for determinism.
_PROFILE_FIELDS: List[Tuple[str, str]] = [
    ("legal_name", "Legal name"),
    ("operating_name", "Operating name"),
    ("former_name", "Former name"),
    ("industry", "Industry"),
    ("company_type", "Type"),
    ("city", "City"),
    ("province", "Province"),
    ("country", "Country"),
    ("website", "Website"),
    ("year_incorporated", "Year incorporated"),
    ("business_number", "Business number"),
    ("source_system", "Source system"),
    ("source_id", "Source id"),
]

MAX_INTERACTIONS = 3


class BriefError(Exception):
    """A brief could not be built (e.g. the company id is unknown)."""


# --------------------------------------------------------------------------- #
# Record helpers
# --------------------------------------------------------------------------- #

def _records(document: Dict[str, Any], data_type: str) -> List[Dict[str, Any]]:
    return document.get("records", {}).get(data_type, [])


def _fields(record: Dict[str, Any]) -> Dict[str, Any]:
    return record.get("fields", {})


def _index_by_company_ref(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        ref = _fields(record).get("company_ref")
        if ref is not None:
            index.setdefault(str(ref), []).append(record)
    return index


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _resolve_rung(track_slug: Optional[str], order: Optional[int]) -> Optional[Dict[str, Any]]:
    if not track_slug or order is None:
        return None
    for track in contract.tracks()["tracks"]:
        if track["slug"] == track_slug:
            rungs = track["rungs"]
            for rung in rungs:
                if int(rung["order"]) == int(order):
                    return {
                        "track_name": track.get("name", track_slug),
                        "rung_name": rung.get("name", f"rung {order}"),
                        "funder_stage": rung.get("funder_stage"),
                        "objective_signal": rung.get("objective_signal"),
                        "order": int(order),
                        "total": len(rungs),
                    }
    return None


def _company_flags(document: Dict[str, Any], company_id: str) -> List[Dict[str, str]]:
    """Open flags attached to this company across the records document.

    Includes document-level flags whose ``identity`` is the company id and any
    per-record flags carried on records that reference the company.
    """
    out: List[Dict[str, str]] = []
    for flag in document.get("flags", []):
        if _str(flag.get("identity")) == company_id:
            out.append({
                "flag": _str(flag.get("flag")) or "flag",
                "detail": _str(flag.get("detail")),
            })
    return out


def _track_lines(document: Dict[str, Any], company_id: str) -> Tuple[str, str]:
    positions = _index_by_company_ref(_records(document, "milestone_position")).get(company_id, [])
    targets = _index_by_company_ref(_records(document, "milestone_target")).get(company_id, [])

    position_text = "Not set"
    if positions:
        fields = _fields(positions[0])
        rung = _resolve_rung(fields.get("track"), fields.get("rung_order"))
        if rung:
            stage = f" · funder stage {rung['funder_stage']}" if rung.get("funder_stage") else ""
            position_text = (
                f"{rung['track_name']} track: {rung['rung_name']} "
                f"(rung {rung['order']} of {rung['total']}){stage}"
            )
            as_of = _str(fields.get("as_of_date"))
            if as_of:
                position_text += f", as of {as_of}"
        else:
            position_text = f"Track {_str(fields.get('track'))}, rung {_str(fields.get('rung_order'))}"

    target_text = "Not set"
    if targets:
        fields = _fields(targets[0])
        rung = _resolve_rung(fields.get("track"), fields.get("target_rung_order"))
        signal = _str(fields.get("objective_signal"))
        if rung:
            target_text = f"{rung['rung_name']} (rung {rung['order']} of {rung['total']})"
        else:
            target_text = f"Rung {_str(fields.get('target_rung_order'))}"
        if signal:
            target_text += f" — {signal}"

    return position_text, target_text


def _sorted_interactions(document: Dict[str, Any], company_id: str) -> List[Dict[str, Any]]:
    records = _index_by_company_ref(_records(document, "interaction")).get(company_id, [])
    # Most recent first; break ties by identity for a stable order.
    records.sort(key=lambda r: (_str(_fields(r).get("occurred_at")), _str(r.get("identity"))), reverse=True)
    rows = []
    for record in records[:MAX_INTERACTIONS]:
        fields = _fields(record)
        rows.append({
            "date": _str(fields.get("occurred_at")),
            "type": _str(fields.get("interaction_type")),
            "subject": _str(fields.get("subject")) or _str(fields.get("notes")),
        })
    return rows


def _company_name(fields: Dict[str, Any]) -> str:
    return _str(fields.get("operating_name")) or _str(fields.get("legal_name")) or _str(fields.get("source_id"))


# --------------------------------------------------------------------------- #
# A2UI blueprint helpers
# --------------------------------------------------------------------------- #

def _msg(payload_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"version": PROTOCOL_VERSION, payload_key: payload}


def _text(comp_id: str, text: Any, variant: Optional[str] = None) -> Dict[str, Any]:
    comp: Dict[str, Any] = {"id": comp_id, "component": "Text", "text": text}
    if variant:
        comp["variant"] = variant
    return comp


# --------------------------------------------------------------------------- #
# Company brief
# --------------------------------------------------------------------------- #

def build_company_brief(document: Dict[str, Any], company_id: str) -> Dict[str, Any]:
    companies = {str(r.get("identity")): r for r in _records(document, "company")}
    record = companies.get(company_id)
    if record is None:
        known = ", ".join(sorted(companies)) or "(none)"
        raise BriefError(f"no company with id {company_id!r} in records; known ids: {known}")

    fields = _fields(record)
    name = _company_name(fields)
    period = _str(document.get("period"))
    subtitle = "Company brief"
    if period:
        subtitle += f" · period {period}"
    source_system = _str(fields.get("source_system"))
    if source_system:
        subtitle += f" · {source_system}"

    profile_rows = [
        {"field": label, "value": _str(fields.get(key))}
        for key, label in _PROFILE_FIELDS
        if _str(fields.get(key))
    ]
    position_text, target_text = _track_lines(document, company_id)
    interactions = _sorted_interactions(document, company_id)
    flags = _company_flags(document, company_id)

    data_model = {
        "company": {"name": name, "subtitle": subtitle},
        "profile": profile_rows,
        "track": {"position": position_text, "target": target_text},
        "interactions": interactions,
        "flags": flags,
    }

    # Component tree.
    interactions_content_id = "interactions-table" if interactions else "interactions-empty"
    flags_content_id = "flags-table" if flags else "flags-empty"

    components: List[Dict[str, Any]] = [
        {"id": "root", "component": "Column",
         "children": ["heading", "subtitle", "profile-card", "track-card", "interactions-card", "flags-card"]},
        _text("heading", {"path": "/company/name"}, "h1"),
        _text("subtitle", {"path": "/company/subtitle"}, "muted"),

        {"id": "profile-card", "component": "Card", "child": "profile-body"},
        {"id": "profile-body", "component": "Column", "children": ["profile-title", "profile-table"]},
        _text("profile-title", "Profile", "h2"),
        {"id": "profile-table", "component": "Table",
         "columns": [{"key": "field", "label": "Field"}, {"key": "value", "label": "Value"}],
         "rows": {"path": "/profile"}},

        {"id": "track-card", "component": "Card", "child": "track-body"},
        {"id": "track-body", "component": "Column", "children": ["track-title", "track-position", "track-target"]},
        _text("track-title", "Track position and target", "h2"),
        _text("track-position", {"path": "/track/position"}, "body"),
        _text("track-target", {"path": "/track/target"}, "body"),

        {"id": "interactions-card", "component": "Card", "child": "interactions-body"},
        {"id": "interactions-body", "component": "Column",
         "children": ["interactions-title", interactions_content_id]},
        _text("interactions-title", "Last three interactions", "h2"),

        {"id": "flags-card", "component": "Card", "child": "flags-body"},
        {"id": "flags-body", "component": "Column", "children": ["flags-title", flags_content_id]},
        _text("flags-title", "Open flags", "h2"),
    ]

    if interactions:
        components.append({
            "id": "interactions-table", "component": "Table",
            "columns": [
                {"key": "date", "label": "Date"},
                {"key": "type", "label": "Type"},
                {"key": "subject", "label": "Subject"},
            ],
            "rows": {"path": "/interactions"},
        })
    else:
        components.append(_text("interactions-empty", "No interactions recorded.", "muted"))

    if flags:
        components.append({
            "id": "flags-table", "component": "Table",
            "columns": [{"key": "flag", "label": "Flag"}, {"key": "detail", "label": "Detail"}],
            "rows": {"path": "/flags"},
        })
    else:
        components.append(_text("flags-empty", "No open flags.", "muted"))

    messages = [
        _msg("createSurface", {"surfaceId": COMPANY_SURFACE, "catalogId": CATALOG_ID, "sendDataModel": False}),
        _msg("updateComponents", {"surfaceId": COMPANY_SURFACE, "components": components}),
        _msg("updateDataModel", {"surfaceId": COMPANY_SURFACE, "path": "/", "value": data_model}),
    ]

    markdown = _company_markdown(name, subtitle, profile_rows, position_text, target_text, interactions, flags)
    return {"name": f"company-{_slug(company_id)}", "surface_id": COMPANY_SURFACE,
            "messages": messages, "markdown": markdown, "data_model": data_model}


def _company_markdown(name, subtitle, profile_rows, position_text, target_text, interactions, flags) -> str:
    lines: List[str] = [f"# {name}", "", subtitle, "", "## Profile", ""]
    if profile_rows:
        for row in profile_rows:
            lines.append(f"- **{row['field']}:** {row['value']}")
    else:
        lines.append("No profile fields recorded.")
    lines += ["", "## Track position and target", "",
              f"- **Position:** {position_text}", f"- **Target:** {target_text}",
              "", "## Last three interactions", ""]
    if interactions:
        lines += ["| Date | Type | Subject |", "| --- | --- | --- |"]
        for row in interactions:
            lines.append(f"| {row['date']} | {row['type']} | {row['subject']} |")
    else:
        lines.append("No interactions recorded.")
    lines += ["", "## Open flags", ""]
    if flags:
        for flag in flags:
            detail = f": {flag['detail']}" if flag["detail"] else ""
            lines.append(f"- {flag['flag']}{detail}")
    else:
        lines.append("No open flags.")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Portfolio brief
# --------------------------------------------------------------------------- #

def build_portfolio_brief(document: Dict[str, Any]) -> Dict[str, Any]:
    companies = sorted(_records(document, "company"), key=lambda r: _str(r.get("identity")))
    positions = _index_by_company_ref(_records(document, "milestone_position"))
    targets = _index_by_company_ref(_records(document, "milestone_target"))
    interactions = _index_by_company_ref(_records(document, "interaction"))

    items: List[Dict[str, Any]] = []
    for record in companies:
        company_id = _str(record.get("identity"))
        fields = _fields(record)
        pos_rung = None
        track_name = ""
        if positions.get(company_id):
            pos_fields = _fields(positions[company_id][0])
            track_name = _str(pos_fields.get("track"))
            pos_rung = _resolve_rung(pos_fields.get("track"), pos_fields.get("rung_order"))
        tgt_rung = None
        if targets.get(company_id):
            tgt_fields = _fields(targets[company_id][0])
            tgt_rung = _resolve_rung(tgt_fields.get("track"), tgt_fields.get("target_rung_order"))
        last_interaction = ""
        if interactions.get(company_id):
            last_interaction = max(_str(_fields(r).get("occurred_at")) for r in interactions[company_id])
        items.append({
            "company": _company_name(fields),
            "track": pos_rung["track_name"] if pos_rung else (track_name or "—"),
            "position": pos_rung["rung_name"] if pos_rung else "—",
            "target": tgt_rung["rung_name"] if tgt_rung else "—",
            "last_interaction": last_interaction or "—",
            "open_flags": str(len(_company_flags(document, company_id))),
        })

    period = _str(document.get("period"))
    summary = f"{len(items)} " + ("company" if len(items) == 1 else "companies")
    if period:
        summary += f" in period {period}"
    caption = f"{len(items)} " + ("company" if len(items) == 1 else "companies")

    data_model = {"title": "Portfolio", "summary": summary, "caption": caption, "items": items}

    components = [
        {"id": "root", "component": "Column", "children": ["heading", "summary", "table-card"]},
        _text("heading", {"path": "/title"}, "h1"),
        _text("summary", {"path": "/summary"}, "muted"),
        {"id": "table-card", "component": "Card", "child": "portfolio-table"},
        {"id": "portfolio-table", "component": "Table",
         "caption": {"path": "/caption"},
         "columns": [
             {"key": "company", "label": "Company"},
             {"key": "track", "label": "Track"},
             {"key": "position", "label": "Position"},
             {"key": "target", "label": "Target"},
             {"key": "last_interaction", "label": "Last interaction"},
             {"key": "open_flags", "label": "Open flags"},
         ],
         "rows": {"path": "/items"}},
    ]

    messages = [
        _msg("createSurface", {"surfaceId": PORTFOLIO_SURFACE, "catalogId": CATALOG_ID, "sendDataModel": False}),
        _msg("updateComponents", {"surfaceId": PORTFOLIO_SURFACE, "components": components}),
        _msg("updateDataModel", {"surfaceId": PORTFOLIO_SURFACE, "path": "/", "value": data_model}),
    ]

    markdown = _portfolio_markdown(summary, items)
    return {"name": "portfolio", "surface_id": PORTFOLIO_SURFACE,
            "messages": messages, "markdown": markdown, "data_model": data_model}


def _portfolio_markdown(summary, items) -> str:
    lines: List[str] = ["# Portfolio", "", summary, ""]
    lines += ["| Company | Track | Position | Target | Last interaction | Open flags |",
              "| --- | --- | --- | --- | --- | --- |"]
    for row in items:
        lines.append(
            f"| {row['company']} | {row['track']} | {row['position']} | "
            f"{row['target']} | {row['last_interaction']} | {row['open_flags']} |"
        )
    if not items:
        lines.append("| _No companies in records._ |  |  |  |  |  |")
    return "\n".join(lines) + "\n"


def _slug(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in value.strip()).strip("-") or "company"
