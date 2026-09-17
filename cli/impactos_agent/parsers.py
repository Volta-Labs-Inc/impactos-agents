"""Source parsers: BAI v5 workbook, tabular CSV/XLSX exports, and transcripts.

Each parser normalises a raw source file into a source payload that carries the
vendor id and a sha256 content hash of the original bytes. Parsing invents
nothing: cells and segments are data, and no value is derived from them here.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import xlsx

SOURCE_SCHEMA_VERSION = "1.0.0"

BAI_SHEET_HEADERS = {
    "Companies": [
        "Company ID", "Business Name", "Former Name", "Business Number",
        "Name of Ultimate Founder", "Address", "City", "Province/Territory",
        "Phone Number", "Email", "Website URL", "Industry Sector",
    ],
    "Company Updates": [
        "Update ID", "Company ID", "Update Date", "Current FTEs",
    ],
    "Contacts": ["Contact ID", "Company ID", "First Name", "Last Name"],
    "Programs": ["Program ID", "Program Name"],
    "Program Cohorts": ["Cohort ID", "Program ID", "Company ID"],
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _meta(path: Path, raw: bytes) -> Dict[str, Any]:
    return {
        "source_file": path.name,
        "content_sha256": sha256_bytes(raw),
        "byte_count": len(raw),
    }


# --------------------------------------------------------------------------- #
# Tabular exports (CSV / XLSX) with UTF-8 BOM stripping.
# --------------------------------------------------------------------------- #

def parse_export(path: Path) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    raw = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".csv" or suffix == ".tsv":
        vendor = "csv"
        try:
            # utf-8-sig transparently strips a leading UTF-8 BOM.
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            errors.append(f"{path.name} is not valid UTF-8 ({exc}); re-export as UTF-8")
            return _empty_export_payload(path, raw, vendor), errors
        delimiter = "\t" if suffix == ".tsv" else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        columns = [c.strip() for c in (reader.fieldnames or [])]
        rows = [{(k.strip() if k else k): v for k, v in row.items()} for row in reader]
        sheets = {"default": {"columns": columns, "rows": rows}}
    elif suffix in (".xlsx", ".xlsm"):
        vendor = "xlsx"
        try:
            sheets = xlsx.read_tabular_xlsx(path)
        except Exception as exc:  # noqa: BLE001 - malformed workbook is data, report it
            errors.append(f"{path.name} could not be read as a workbook: {exc}")
            return _empty_export_payload(path, raw, vendor), errors
    else:
        errors.append(f"{path.name}: unsupported export type {suffix!r}")
        return _empty_export_payload(path, raw, "unknown"), errors

    payload = {
        "impactos_source": SOURCE_SCHEMA_VERSION,
        "source_type": "export",
        "vendor": vendor,
        "meta": _meta(path, raw),
        "sheets": sheets,
    }
    return payload, errors


def _empty_export_payload(path: Path, raw: bytes, vendor: str) -> Dict[str, Any]:
    return {
        "impactos_source": SOURCE_SCHEMA_VERSION,
        "source_type": "export",
        "vendor": vendor,
        "meta": _meta(path, raw),
        "sheets": {},
    }


# --------------------------------------------------------------------------- #
# BAI v5 workbook.
# --------------------------------------------------------------------------- #

def parse_bai(path: Path) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    raw = path.read_bytes()
    try:
        sheets = xlsx.read_tabular_xlsx(path)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{path.name} could not be read as a BAI workbook: {exc}")
        sheets = {}
    for sheet_name, required in BAI_SHEET_HEADERS.items():
        if sheet_name not in sheets:
            continue
        present = set(sheets[sheet_name]["columns"])
        missing = [h for h in required if h not in present]
        if missing:
            errors.append(f"BAI sheet {sheet_name!r} missing columns: {missing}")
    if not any(name in sheets for name in BAI_SHEET_HEADERS):
        errors.append("workbook has none of the expected BAI v5 sheets")
    payload = {
        "impactos_source": SOURCE_SCHEMA_VERSION,
        "source_type": "bai_v5_workbook",
        "vendor": "bai_v5",
        "meta": _meta(path, raw),
        "sheets": sheets,
    }
    return payload, errors


# --------------------------------------------------------------------------- #
# Transcripts: Fireflies (json), Granola (md), Fathom (txt).
# --------------------------------------------------------------------------- #

_FATHOM_LINE = re.compile(r"^\d{2}:\d{2}:\d{2}\s+([^:]+):\s*(.*)$")
_ATTENDEE = re.compile(r"([^,(]+?)\s*\(([^)]+@[^)]+)\)")


def detect_transcript_vendor(path: Path, text: str) -> Optional[str]:
    stripped = text.lstrip()
    if path.suffix.lower() == ".json" or stripped.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        if isinstance(data, dict) and "transcript" in data and "meeting_id" in data:
            return "fireflies"
        return None
    lowered = text.lower()
    if "fathom transcript" in lowered:
        return "fathom"
    if "granola" in lowered or stripped.startswith("# "):
        return "granola"
    return None


def parse_transcript(path: Path) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        errors.append(f"{path.name} is not valid UTF-8 ({exc})")
        return _transcript_payload(path, raw, "unknown", {}), errors

    vendor = detect_transcript_vendor(path, text)
    if vendor is None:
        errors.append(f"{path.name}: unrecognised transcript format (not Fireflies/Granola/Fathom)")
        return _transcript_payload(path, raw, "unknown", {}), errors

    if vendor == "fireflies":
        transcript = _parse_fireflies(json.loads(text))
    elif vendor == "granola":
        transcript = _parse_granola(text)
    else:
        transcript = _parse_fathom(text)

    if not transcript.get("source_meeting_id"):
        # Derive a stable id from the content hash when the vendor gives none.
        transcript["source_meeting_id"] = f"{vendor}:{sha256_bytes(raw)[:16]}"
    return _transcript_payload(path, raw, vendor, transcript), errors


def _transcript_payload(path: Path, raw: bytes, vendor: str, transcript: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "impactos_source": SOURCE_SCHEMA_VERSION,
        "source_type": "transcript",
        "vendor": vendor,
        "meta": _meta(path, raw),
        "transcript": transcript,
    }


def _parse_fireflies(data: Dict[str, Any]) -> Dict[str, Any]:
    participants = [
        {"name": p.get("name"), "email": p.get("email")}
        for p in data.get("participants", [])
    ]
    segments = [
        {"speaker": s.get("speaker"), "text": s.get("text")}
        for s in data.get("transcript", [])
    ]
    return {
        "source_meeting_id": data.get("meeting_id"),
        "title": data.get("title"),
        "date": data.get("date"),
        "duration_minutes": data.get("duration_minutes"),
        "participants": participants,
        "segments": segments,
    }


def _parse_granola(text: str) -> Dict[str, Any]:
    title = None
    date = None
    participants: List[Dict[str, Any]] = []
    segments: List[Dict[str, Any]] = []
    for line in text.splitlines():
        if line.startswith("# ") and title is None:
            title = line[2:].strip()
        elif line.lower().startswith("date:"):
            date = line.split(":", 1)[1].strip()
        elif line.lower().startswith("attendees:"):
            for name, email in _ATTENDEE.findall(line):
                participants.append({"name": name.strip(), "email": email.strip()})
        elif line.strip().startswith("- "):
            segments.append({"speaker": None, "text": line.strip()[2:].strip()})
    return {
        "source_meeting_id": None,
        "title": title,
        "date": date,
        "participants": participants,
        "segments": segments,
    }


def _parse_fathom(text: str) -> Dict[str, Any]:
    title = None
    date = None
    participants: List[Dict[str, Any]] = []
    segments: List[Dict[str, Any]] = []
    for line in text.splitlines():
        low = line.lower()
        if low.startswith("meeting:") and title is None:
            title = line.split(":", 1)[1].strip()
        elif low.startswith("date:"):
            date = line.split(":", 1)[1].strip()
        elif low.startswith("participants:"):
            for name, email in _ATTENDEE.findall(line):
                participants.append({"name": name.strip(), "email": email.strip()})
        else:
            match = _FATHOM_LINE.match(line.strip())
            if match:
                segments.append({"speaker": match.group(1).strip(), "text": match.group(2).strip()})
    return {
        "source_meeting_id": None,
        "title": title,
        "date": date,
        "participants": participants,
        "segments": segments,
    }


def detect_source_type(path: Path) -> str:
    """Best-effort source type from the file, used when ``--type`` is omitted."""
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv"):
        return "export"
    if suffix in (".xlsx", ".xlsm"):
        # A BAI workbook has the canonical sheet names; otherwise a generic export.
        try:
            sheets = xlsx.read_tabular_xlsx(path)
        except Exception:  # noqa: BLE001
            return "export"
        if "Companies" in sheets and "Company Updates" in sheets:
            return "bai"
        return "export"
    if suffix in (".json", ".md", ".txt", ".vtt"):
        return "transcript"
    return "export"
