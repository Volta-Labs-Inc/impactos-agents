"""Deterministic helper for the onboarding interview.

The onboarding *skill* carries the judgment: what to ask, how to read a pointed-at
file, what to write. This module only does the bookkeeping the skill cannot do
reliably by hand:

* pick the next unanswered question in declared order, so the skill asks one
  question per turn and resumes exactly where it stopped (SR-02);
* round-trip the interview state to ``workspace/state/interview.json``;
* apply the fixed route rule per data type, treating a source with no stable
  identifier as a missing required field (SR-05).

It makes no model or network calls and writes only under the git-ignored
``workspace/`` tree.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

STATE_VERSION = "1.0.0"

# Route rule -------------------------------------------------------------------
#
# Reference / master data that lives authoritatively in an existing system and is
# exported and re-mapped each period. Keep it where it is.
ROUTE_STAY = {
    "organisation",
    "company",
    "person",
    "company_person",
    "program",
    "cohort",
    "membership",
    "company_update",
    "milestone_position",
    "milestone_target",
    "team_member_period",
}
# Data with no authoritative home system; it must accumulate in the optional store.
ROUTE_STORE = {"interaction", "submission"}
# Funding can live in a source system or not; the recommendation is conditional.
ROUTE_CONDITIONAL = {"funding_event"}


class InterviewError(Exception):
    """A bookkeeping failure (unknown question, malformed state)."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# State ------------------------------------------------------------------------

def new_state() -> Dict[str, Any]:
    return {"interview_version": STATE_VERSION, "answers": {}, "updated_at": _now()}


def load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return new_state()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InterviewError(f"interview state at {path} is not valid JSON: {exc}")
    state.setdefault("answers", {})
    return state


def save_state(path: Path, state: Dict[str, Any]) -> None:
    state["updated_at"] = _now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _question_ids(questions: List[Dict[str, Any]]) -> List[str]:
    return [q["id"] for q in questions]


def record_answer(state: Dict[str, Any], question_id: str, value: Any, questions: List[Dict[str, Any]]) -> None:
    if question_id not in _question_ids(questions):
        raise InterviewError(f"unknown question id {question_id!r}")
    state.setdefault("answers", {})[question_id] = {"value": value, "answered_at": _now()}


def next_question(questions: List[Dict[str, Any]], state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the earliest question, in declared order, that has no answer yet."""
    answered = state.get("answers", {})
    for question in questions:
        if question["id"] not in answered:
            return question
    return None


def answered_ids(questions: List[Dict[str, Any]], state: Dict[str, Any]) -> List[str]:
    answered = state.get("answers", {})
    return [q["id"] for q in questions if q["id"] in answered]


def remaining_ids(questions: List[Dict[str, Any]], state: Dict[str, Any]) -> List[str]:
    answered = state.get("answers", {})
    return [q["id"] for q in questions if q["id"] not in answered]


# Questions --------------------------------------------------------------------

def load_questions(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    questions = data.get("questions", data if isinstance(data, list) else [])
    if not questions:
        raise InterviewError(f"no questions found in {path}")
    seen = set()
    for question in questions:
        qid = question.get("id")
        if not qid:
            raise InterviewError("every question must declare an id")
        if qid in seen:
            raise InterviewError(f"duplicate question id {qid!r}")
        seen.add(qid)
    return questions


# Route rule -------------------------------------------------------------------

def recommend_route(data_type: str, source_present: bool = True, has_stable_identifier: bool = True) -> Dict[str, Any]:
    """Recommend a route for one data type. Deterministic; see module docstring."""
    if not source_present:
        return {
            "recommendation": "store",
            "reason": (
                "No existing system holds this data type, so if the organisation "
                "wants to report it, it must live in the optional store."
            ),
            "missing_fields": [],
        }
    if not has_stable_identifier:
        return {
            "recommendation": "store_or_add_identifier",
            "reason": (
                "This source has no stable identifier. A stable identifier is a "
                "required field for re-mapping a source every period, so its "
                "absence is a missing required field: either move this data type "
                "into the optional store (which assigns a stable identifier) or add "
                "a stable identifier column to the source."
            ),
            "missing_fields": ["stable_identifier"],
        }
    if data_type in ROUTE_STORE:
        return {
            "recommendation": "store",
            "reason": (
                "This data type has no authoritative home system; accumulate it in "
                "the optional store so it survives across periods."
            ),
            "missing_fields": [],
        }
    if data_type in ROUTE_CONDITIONAL:
        return {
            "recommendation": "conditional",
            "reason": (
                "Funding stays in the existing system only if that system keeps the "
                "full dated history with stable identifiers and declared amounts; "
                "otherwise move it to the optional store. A person decides."
            ),
            "missing_fields": [],
        }
    if data_type in ROUTE_STAY:
        return {
            "recommendation": "stay",
            "reason": (
                "This data type lives authoritatively in an existing system; keep it "
                "there and export and re-map it each period."
            ),
            "missing_fields": [],
        }
    return {
        "recommendation": "review",
        "reason": "Unrecognised data type; a person must decide where it lives.",
        "missing_fields": [],
    }


def routes_from_source_map(source_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compute a recommendation for every present data type in a source map.

    Each ``data_types`` entry may declare ``present``, ``has_stable_identifier``,
    ``source`` and an already-``route`` chosen by a person. The chosen route is
    compared to the recommendation so a deliberate override is visible.
    """
    rows: List[Dict[str, Any]] = []
    for data_type, spec in sorted(source_map.get("data_types", {}).items()):
        present = bool(spec.get("present", True))
        if not present:
            continue
        has_id = bool(spec.get("has_stable_identifier", True))
        recommendation = recommend_route(data_type, source_present=present, has_stable_identifier=has_id)
        chosen = spec.get("route")
        rows.append({
            "data_type": data_type,
            "source": spec.get("source"),
            "present": present,
            "has_stable_identifier": has_id,
            "recommendation": recommendation["recommendation"],
            "reason": recommendation["reason"],
            "missing_fields": recommendation["missing_fields"],
            "chosen_route": chosen,
            "matches_recommendation": chosen is None or chosen == recommendation["recommendation"],
        })
    return rows
