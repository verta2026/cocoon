"""AskUserQuestion bridge: hook-fed pending state + TUI keystroke driving.

Detection deliberately does NOT parse the session jsonl: Claude Code writes
the tool_use row and its result together at resolution (timestamps
back-dated), so the open question only ever exists in the PreToolUse hook.
"""

import json
import tempfile
import time
import unittest
from pathlib import Path

from bridge.ask import drive_answer, pending_ask
from hooks.ask_pending import handle as hook_handle


QUESTIONS = [
    {
        "question": "Which one?",
        "header": "Pick",
        "multiSelect": False,
        "options": [
            {"label": "A", "description": "first"},
            {"label": "B", "description": "second"},
            {"label": "C", "description": "third"},
        ],
    }
]


def _pre_event(questions=QUESTIONS):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "AskUserQuestion",
        "session_id": "s1",
        "tool_input": {"questions": questions},
    }


class PendingAskTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.state = Path(self.dir.name) / ".ask_pending.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_hook_written_question_is_pending(self):
        hook_handle(_pre_event(), state_file=self.state)
        got = pending_ask(self.state)
        self.assertIsNotNone(got)
        self.assertTrue(got["id"].startswith("ask-"))
        self.assertEqual(got["questions"][0]["question"], "Which one?")

    def test_post_tool_use_clears_pending(self):
        hook_handle(_pre_event(), state_file=self.state)
        hook_handle(
            {"hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion"},
            state_file=self.state,
        )
        self.assertIsNone(pending_ask(self.state))

    def test_user_prompt_submit_clears_pending(self):
        # declining in the terminal never fires PostToolUse; any new input
        # (UserPromptSubmit) must clean up instead
        hook_handle(_pre_event(), state_file=self.state)
        hook_handle({"hook_event_name": "UserPromptSubmit"}, state_file=self.state)
        self.assertIsNone(pending_ask(self.state))

    def test_other_tools_do_not_write_state(self):
        hook_handle(
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {}},
            state_file=self.state,
        )
        self.assertIsNone(pending_ask(self.state))

    def test_expired_entry_is_ghost(self):
        self.state.write_text(
            json.dumps({"id": "ask-1", "ts": time.time() - 901, "questions": QUESTIONS}),
            encoding="utf-8",
        )
        self.assertIsNone(pending_ask(self.state))

    def test_missing_or_malformed_file_is_none(self):
        self.assertIsNone(pending_ask(self.state))
        self.assertIsNone(pending_ask(None))
        self.state.write_text("not json", encoding="utf-8")
        self.assertIsNone(pending_ask(self.state))


class _Screen:
    def __init__(self, stdout):
        self.stdout = stdout


class DriveAnswerTest(unittest.TestCase):
    """Key sequences verified live against Claude Code v2.1.195."""

    def setUp(self):
        self.keys = []
        self.screens = []  # consumed by capture-pane calls; empty -> ""

    def _run(self, cmd, check=False, capture_output=False, text=False):
        if "capture-pane" in cmd:
            return _Screen(self.screens.pop(0) if self.screens else "")
        self.keys.append(cmd[4:])

    def test_single_select_submits_directly(self):
        drive_answer("s", QUESTIONS, [{"index": 2}], run_func=self._run, sleep_func=lambda s: None)
        # no review page for a lone single-select question
        self.assertEqual(self.keys, [["Down"], ["Down"], ["Enter"]])

    def test_multi_select_walks_to_submit_row_then_review(self):
        multi = [dict(QUESTIONS[0], multiSelect=True)]
        self.screens = ["Ready to submit your answers?"]
        drive_answer("s", multi, [{"indexes": [0, 2]}], run_func=self._run, sleep_func=lambda s: None)
        self.assertEqual(
            self.keys,
            [
                ["Space"],  # toggle row 0
                ["Down"],   # row 1
                ["Down"], ["Space"],  # row 2 toggled
                ["Down"],   # "Type something." row
                ["Down"],   # Submit row
                ["Enter"],  # submit -> review page
                ["Enter"],  # confirm review
            ],
        )

    def test_other_types_in_place_without_leading_enter(self):
        drive_answer("s", QUESTIONS, [{"other": "custom"}], run_func=self._run, sleep_func=lambda s: None)
        # Enter before typing would decline the whole question
        self.assertEqual(
            self.keys,
            [["Down"], ["Down"], ["Down"], ["-l", "custom"], ["Enter"]],
        )

    def test_multi_select_other_confirms_text_then_submits(self):
        multi = [dict(QUESTIONS[0], multiSelect=True)]
        self.screens = ["Ready to submit your answers?"]
        drive_answer("s", multi, [{"other": "hi"}], run_func=self._run, sleep_func=lambda s: None)
        self.assertEqual(
            self.keys,
            [
                ["Down"], ["Down"],  # walk option rows (nothing toggled)
                ["Down"],            # "Type something." row
                ["-l", "hi"], ["Enter"],
                ["Down"],            # Submit row
                ["Enter"],           # submit -> review page
                ["Enter"],           # confirm review
            ],
        )

    def test_two_questions_end_with_one_review(self):
        multi = dict(QUESTIONS[0], multiSelect=True)
        self.screens = ["Ready to submit your answers?"]
        drive_answer(
            "s",
            QUESTIONS + [multi],
            [{"index": 0}, {"indexes": [1]}],
            run_func=self._run,
            sleep_func=lambda s: None,
        )
        self.assertEqual(
            self.keys,
            [
                ["Enter"],            # q1: pick option 0, auto-advance
                ["Down"], ["Space"],  # q2: toggle row 1
                ["Down"],             # row 2
                ["Down"],             # "Type something." row
                ["Down"],             # Submit row
                ["Enter"],            # submit -> review page
                ["Enter"],            # confirm review
            ],
        )

    def test_review_loop_stops_when_selector_is_gone(self):
        self.screens = ["Esc to cancel", ""]
        drive_answer("s", QUESTIONS, [{"index": 0}], run_func=self._run, sleep_func=lambda s: None)
        # first capture still shows the selector, second shows it gone: no stray Enter
        self.assertEqual(self.keys, [["Enter"]])


if __name__ == "__main__":
    unittest.main()
