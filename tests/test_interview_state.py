"""SR-02: the onboarding interview asks one question per turn and resumes at the
next unanswered question with earlier answers intact.

These tests drive the deterministic ``impactos interview`` helper (next-question
selection, answer round-trip, resume) that the onboarding skill relies on. The
judgment (what to do with an answer) lives in the skill; only the bookkeeping is
tested here.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import impactos_support as support
from impactos_agent import interview


QUESTIONS = [
    {"id": "org_name", "section": "Inventory", "prompt": "Organisation name?", "required": True},
    {"id": "period", "section": "Inventory", "prompt": "Reporting period?", "required": True},
    {"id": "company_source", "section": "Source map", "prompt": "Where do companies live?", "required": True},
]


def _write_questions(tmp: Path) -> Path:
    path = tmp / "questions.json"
    path.write_text(json.dumps({"interview_version": "1.0.0", "questions": QUESTIONS}), encoding="utf-8")
    return path


class NextQuestionTests(unittest.TestCase):
    def test_first_question_when_no_state(self):
        state = interview.new_state()
        nxt = interview.next_question(QUESTIONS, state)
        self.assertEqual(nxt["id"], "org_name")

    def test_skips_answered_and_returns_next(self):
        state = interview.new_state()
        interview.record_answer(state, "org_name", "Harbourline", QUESTIONS)
        nxt = interview.next_question(QUESTIONS, state)
        self.assertEqual(nxt["id"], "period")

    def test_none_when_complete(self):
        state = interview.new_state()
        for q in QUESTIONS:
            interview.record_answer(state, q["id"], "x", QUESTIONS)
        self.assertIsNone(interview.next_question(QUESTIONS, state))

    def test_out_of_order_answer_still_advances_in_order(self):
        # Answering a later question does not change that the next unanswered is
        # still the earliest unanswered one, in declared order.
        state = interview.new_state()
        interview.record_answer(state, "company_source", "CRM export", QUESTIONS)
        nxt = interview.next_question(QUESTIONS, state)
        self.assertEqual(nxt["id"], "org_name")

    def test_unknown_question_id_is_rejected(self):
        state = interview.new_state()
        with self.assertRaises(interview.InterviewError):
            interview.record_answer(state, "not_a_question", "x", QUESTIONS)


class RoundTripTests(unittest.TestCase):
    def test_state_survives_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            questions = _write_questions(project)

            r1 = support.run(
                "interview", action="answer", id="org_name", value="Harbourline",
                questions=str(questions), source_map=None, project_root=project,
            )
            self.assertEqual(r1.exit_code, 0, msg=r1.errors)
            # Fresh process would reload from disk; simulate by reading state back.
            r2 = support.run(
                "interview", action="next", id=None, value=None,
                questions=str(questions), source_map=None, project_root=project,
            )
            self.assertEqual(r2.data["next_question"]["id"], "period")
            self.assertEqual(r2.data["answered"], ["org_name"])

    def test_resume_reports_answered_and_remaining(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            questions = _write_questions(project)
            support.run("interview", action="answer", id="org_name", value="Harbourline",
                        questions=str(questions), source_map=None, project_root=project)
            support.run("interview", action="answer", id="period", value="2026-06-30",
                        questions=str(questions), source_map=None, project_root=project)
            status = support.run("interview", action="status", id=None, value=None,
                                 questions=str(questions), source_map=None, project_root=project)
            self.assertEqual(status.data["answered"], ["org_name", "period"])
            self.assertEqual(status.data["remaining"], ["company_source"])
            self.assertFalse(status.data["complete"])

    def test_answer_persists_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            questions = _write_questions(project)
            support.run("interview", action="answer", id="org_name", value="Harbourline",
                        questions=str(questions), source_map=None, project_root=project)
            state_file = project / "workspace" / "state" / "interview.json"
            self.assertTrue(state_file.exists())
            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["answers"]["org_name"]["value"], "Harbourline")


if __name__ == "__main__":
    unittest.main()
