"""Value normalisers, lifted and adapted from the BAI import helper.

These are pure, deterministic transforms. They never infer a value that is not
present in the source: a blank stays blank, an unrecognised vocabulary value is
reported, never guessed.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional, Tuple


def normalize_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_date(value: Any) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(iso_date, error)``. ``error`` is a message when unparseable."""
    if value is None or value == "":
        return None, None
    if isinstance(value, datetime):
        return value.date().isoformat(), None
    if isinstance(value, date):
        return value.isoformat(), None
    text = str(value).strip()
    if not text:
        return None, None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat(), None
        except ValueError:
            continue
    return None, f"could not parse {text!r} as a date"


def normalize_number(value: Any) -> Tuple[Optional[float], Optional[str]]:
    if value is None or value == "":
        return None, None
    if isinstance(value, bool):
        # A boolean is never a number here.
        return None, f"expected a number, got boolean {value!r}"
    if isinstance(value, (int, float)):
        return value, None
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text:
        return None, None
    try:
        return (float(text) if "." in text else int(text)), None
    except ValueError:
        return None, f"could not parse {text!r} as a number"


def normalize_yes_no(value: Any) -> Optional[bool]:
    """Return True/False for an explicit yes/no cell, else None (never inferred)."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("yes", "y", "true", "1"):
        return True
    if text in ("no", "n", "false", "0"):
        return False
    return None


def normalize_vocabulary(value: Any, vocabulary) -> Tuple[Optional[str], Optional[str]]:
    """Match a cell to a controlled vocabulary, case-insensitively.

    Returns ``(canonical_value, error)``. An unrecognised value is reported, not
    coerced or guessed.
    """
    text = normalize_str(value)
    if text is None:
        return None, None
    lowered = {str(v).strip().lower(): v for v in vocabulary}
    if text.lower() in lowered:
        return lowered[text.lower()], None
    return None, f"{text!r} is not in the allowed vocabulary {list(vocabulary)!r}"


def split_name(value: Any) -> Tuple[Optional[str], Optional[str]]:
    """Split a full name into ``(first, last)`` on the first space.

    A single token becomes the first name with no last name. This is a mechanical
    split of a value that is already present; it invents nothing.
    """
    text = normalize_str(value)
    if text is None:
        return None, None
    parts = text.split()
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def join_name(first: Any, last: Any) -> Optional[str]:
    parts = [normalize_str(first), normalize_str(last)]
    joined = " ".join(p for p in parts if p)
    return joined or None
