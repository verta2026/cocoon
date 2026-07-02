import unittest

from bridge.forge_turns import close_at_final_assistant, has_text_content


class ForgeTurnsTest(unittest.TestCase):
    def test_keeps_events_when_final_event_is_assistant(self):
        events = [{"type": "user"}, {"type": "assistant", "message": {"content": [{"type": "text", "text": "ok"}]}}]

        selection = close_at_final_assistant(events)

        self.assertEqual(selection.kept, events)
        self.assertEqual(selection.trimmed_tail, [])
        self.assertEqual(selection.warnings, [])
        self.assertEqual(selection.terminal_type_before_trim, "assistant")
        self.assertEqual(selection.terminal_type, "assistant")

    def test_trims_trailing_events_after_final_text_assistant(self):
        events = [
            {"type": "user", "message": {"content": [{"type": "text", "text": "hi"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "reply"}]}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tool"}]}},
            {"type": "user", "message": {"content": [{"type": "text", "text": "open"}]}},
        ]

        selection = close_at_final_assistant(events, allow_open_turn=True)

        self.assertEqual(selection.kept, events[:2])
        self.assertEqual(selection.trimmed_tail, events[2:])
        self.assertEqual(selection.terminal_type_before_trim, "user")
        self.assertEqual(selection.terminal_type, "assistant")
        self.assertEqual(len(selection.warnings), 2)
        self.assertTrue(selection.warnings[0].startswith("trimmed 2 trailing event"))
        self.assertIn("allow_open_turn", selection.warnings[1])

    def test_requires_a_text_bearing_assistant_event(self):
        with self.assertRaisesRegex(ValueError, "no text-bearing assistant"):
            close_at_final_assistant([{"type": "user"}, {"type": "assistant", "message": {"content": [{"type": "tool_use"}]}}])

    def test_has_text_content_handles_string_and_blocks(self):
        self.assertTrue(has_text_content({"message": {"content": "plain"}}))
        self.assertTrue(has_text_content({"message": {"content": [{"type": "text", "text": ""}]}}))
        self.assertFalse(has_text_content({"message": {"content": [{"type": "tool_use", "id": "x"}]}}))


if __name__ == "__main__":
    unittest.main()
