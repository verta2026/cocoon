import unittest

from bridge.forge_summary_injection import inject_summary_event, synthetic_summary_event


class ForgeSummaryInjectionTest(unittest.TestCase):
    def test_synthetic_summary_event_uses_template_but_removes_request_id(self):
        template = {"type": "user", "requestId": "private", "custom": {"nested": True}}

        event = synthetic_summary_event(" remembered ", template, "FORGE_CONTEXT_SUMMARY:")

        self.assertEqual(event["type"], "user")
        self.assertFalse(event["isMeta"])
        self.assertNotIn("requestId", event)
        self.assertEqual(event["custom"], {"nested": True})
        text = event["message"]["content"][0]["text"]
        self.assertTrue(text.startswith("FORGE_CONTEXT_SUMMARY:\n"))
        self.assertIn("remembered", text)

    def test_inject_summary_event_prefers_user_template(self):
        kept = [{"type": "assistant", "requestId": "assistant"}, {"type": "user", "requestId": "user"}]

        events, injected = inject_summary_event(kept, "summary", "MARKER:")

        self.assertTrue(injected)
        self.assertEqual(len(events), 3)
        self.assertEqual(events[1:], kept)
        self.assertEqual(events[0]["type"], "user")
        self.assertNotIn("requestId", events[0])

    def test_inject_summary_event_skips_empty_summary_or_empty_events(self):
        kept = [{"type": "user"}]

        events, injected = inject_summary_event(kept, "   ", "MARKER:")
        self.assertFalse(injected)
        self.assertIs(events, kept)

        events, injected = inject_summary_event([], "summary", "MARKER:")
        self.assertFalse(injected)
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
