"""Loaders and small lookups over the issue #2 contract artifacts."""

from __future__ import annotations

import functools
import json
from typing import Any, Dict, List, Optional

from . import paths


@functools.lru_cache(maxsize=None)
def _load(path_str: str) -> Dict[str, Any]:
    with open(path_str, "r", encoding="utf-8") as handle:
        return json.load(handle)


def data_contract() -> Dict[str, Any]:
    return _load(str(paths.DATA_CONTRACT))


def tracks() -> Dict[str, Any]:
    return _load(str(paths.TRACKS))


def reporting_profile() -> Dict[str, Any]:
    return _load(str(paths.REPORTING_PROFILE))


def bai_export_contract() -> Dict[str, Any]:
    return _load(str(paths.BAI_EXPORT_CONTRACT))


def data_type_fields(data_type: str) -> Dict[str, Any]:
    return data_contract()["data_types"][data_type]["fields"]


def field_classification(data_type: str, field: str) -> Optional[str]:
    fields = data_type_fields(data_type)
    if field in fields:
        return fields[field].get("classification")
    return None


# Fields whose value must come only from a source column that declares it, never
# from a name, free-text, stage or the absence of data (AGENTS.md never-infer).
NEVER_INFER_CLASSIFICATIONS = {"demographic"}
NEVER_INFER_FIELDS = {("company", "company_type"), ("funding_event", "funding_type"), ("funding_event", "amount")}


def funder_stage_for(track_slug: str, rung_order: int) -> Optional[str]:
    """Forward lookup: a track position -> the funder stage (unambiguous)."""
    for track in tracks()["tracks"]:
        if track["slug"] == track_slug:
            for rung in track["rungs"]:
                if int(rung["order"]) == int(rung_order):
                    return rung.get("funder_stage")
    return None


def lowest_rung_for_funder_stage(track_slug: str, funder_stage: str) -> Optional[int]:
    """Reverse lookup used only with an author-declared track constant.

    Returns the lowest rung order on the track whose funder_stage matches. Because
    every rung with a given funder_stage shares that stage, exporting the chosen
    rung reproduces the reported stage exactly. Deterministic; no inference of the
    track (the mapping author declares it).
    """
    candidates: List[int] = []
    for track in tracks()["tracks"]:
        if track["slug"] == track_slug:
            for rung in track["rungs"]:
                if rung.get("funder_stage") == funder_stage:
                    candidates.append(int(rung["order"]))
    return min(candidates) if candidates else None
