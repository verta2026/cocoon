import unittest

from bridge.claude_session import (
    mark_session_launch,
    new_pick_state,
    pick_session_jsonl,
)


class ClaudeSessionPickTest(unittest.TestCase):
    def test_pins_newest_on_first_pick(self):
        state = new_pick_state()
        picked = pick_session_jsonl([("a.jsonl", 100.0), ("b.jsonl", 200.0)], state)
        self.assertEqual(picked, "b.jsonl")
        self.assertEqual(state["pinned"], "b.jsonl")

    def test_pinned_file_survives_newer_rival(self):
        # A second Claude session in the same workdir writes a newer file;
        # the UI must not silently switch conversations.
        state = new_pick_state()
        pick_session_jsonl([("mine.jsonl", 100.0)], state)
        picked = pick_session_jsonl(
            [("mine.jsonl", 100.0), ("rival.jsonl", 999.0)], state
        )
        self.assertEqual(picked, "mine.jsonl")

    def test_relaunch_rebinds_to_post_launch_file(self):
        state = new_pick_state()
        pick_session_jsonl([("old.jsonl", 100.0)], state)
        mark_session_launch(state, now=500.0)
        picked = pick_session_jsonl(
            [("old.jsonl", 100.0), ("new.jsonl", 501.0)], state
        )
        self.assertEqual(picked, "new.jsonl")
        self.assertEqual(state["pinned"], "new.jsonl")

    def test_interim_fallback_does_not_pin(self):
        # Right after a relaunch the new session's file may not exist yet:
        # serve the newest available but stay unpinned so the next poll can
        # still bind to the real one.
        state = new_pick_state()
        mark_session_launch(state, now=500.0)
        picked = pick_session_jsonl([("old.jsonl", 100.0)], state)
        self.assertEqual(picked, "old.jsonl")
        self.assertIsNone(state["pinned"])
        picked = pick_session_jsonl(
            [("old.jsonl", 100.0), ("new.jsonl", 502.0)], state
        )
        self.assertEqual(picked, "new.jsonl")
        self.assertEqual(state["pinned"], "new.jsonl")

    def test_vanished_pin_repicks(self):
        state = new_pick_state()
        pick_session_jsonl([("gone.jsonl", 100.0)], state)
        picked = pick_session_jsonl([("other.jsonl", 50.0)], state)
        self.assertEqual(picked, "other.jsonl")
        self.assertEqual(state["pinned"], "other.jsonl")

    def test_empty_dir_returns_none(self):
        state = new_pick_state()
        self.assertIsNone(pick_session_jsonl([], state))
        self.assertIsNone(state["pinned"])


if __name__ == "__main__":
    unittest.main()
