import unittest

from bridge.forge_handoff import build_handoff_state


def user(text, timestamp=""):
    return {
        "type": "user",
        "timestamp": timestamp,
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def assistant(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


class ForgeHandoffTest(unittest.TestCase):
    def test_build_handoff_state_closes_tail_and_prepares_replay(self):
        window = {
            "kept": [user("start", "t0"), assistant("reply"), user("open question", "t2")],
            "grew_backward": True,
            "dialogue_start_index": 0,
            "tool_pair_repairs": 2,
        }

        state = build_handoff_state(
            window,
            [{"path": "newer.jsonl"}],
            allow_open_turn=True,
            replay_created_at="now",
        )

        self.assertEqual(state["kept"], window["kept"][:2])
        self.assertEqual(state["trimmed_tail"], window["kept"][2:])
        self.assertEqual(state["terminal_type_before_trim"], "user")
        self.assertEqual(state["terminal_type"], "assistant")
        self.assertEqual(
            state["replay"],
            {
                "new_sid": "",
                "created_at": "now",
                "messages": [{"timestamp": "t2", "text": "open question"}],
            },
        )
        self.assertEqual(len(state["warnings"]), 6)
        self.assertTrue(state["warnings"][0].startswith("trimmed 1 trailing event"))
        self.assertIn("allow_open_turn", state["warnings"][1])
        self.assertIn("grew dialogue zone backward", state["warnings"][2])
        self.assertIn("repaired 2 event", state["warnings"][3])
        self.assertIn("skipped 1 newer candidate", state["warnings"][4])
        self.assertIn("queued for replay", state["warnings"][5])

    def test_build_handoff_state_keeps_clean_closed_window(self):
        window = {
            "kept": [user("start"), assistant("reply")],
            "grew_backward": False,
            "dialogue_start_index": 0,
            "tool_pair_repairs": 0,
        }

        state = build_handoff_state(window, [], replay_created_at="now")

        self.assertEqual(state["kept"], window["kept"])
        self.assertEqual(state["trimmed_tail"], [])
        self.assertEqual(state["warnings"], [])
        self.assertIsNone(state["replay"])
        self.assertEqual(state["terminal_type"], "assistant")


if __name__ == "__main__":
    unittest.main()
