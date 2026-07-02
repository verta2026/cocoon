import unittest

from bridge.forge_turns import close_at_final_assistant


class ForgeTurnsTest(unittest.TestCase):
    def test_keeps_events_when_final_event_is_assistant(self):
        events = [{"type": "user"}, {"type": "assistant"}]

        selection = close_at_final_assistant(events)

        self.assertEqual(selection.kept, events)
        self.assertEqual(selection.warnings, [])
        self.assertEqual(selection.terminal_type_before_trim, "assistant")
        self.assertEqual(selection.terminal_type, "assistant")

    def test_trims_trailing_non_assistant_events(self):
        events = [{"type": "user"}, {"type": "assistant"}, {"type": "user"}]

        selection = close_at_final_assistant(events, allow_open_turn=True)

        self.assertEqual(selection.kept, events[:2])
        self.assertEqual(selection.terminal_type_before_trim, "user")
        self.assertEqual(selection.terminal_type, "assistant")
        self.assertEqual(len(selection.warnings), 2)
        self.assertTrue(selection.warnings[0].startswith("trimmed 1 trailing non-assistant event"))
        self.assertIn("allow_open_turn", selection.warnings[1])

    def test_requires_an_assistant_event(self):
        with self.assertRaisesRegex(ValueError, "no assistant message"):
            close_at_final_assistant([{"type": "user"}])


if __name__ == "__main__":
    unittest.main()
