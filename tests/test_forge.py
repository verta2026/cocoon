import unittest

from bridge.forge import (
    content_blocks,
    estimate_tokens,
    event_text,
    filter_runtime_noise_turns,
    is_real_user,
    sanitize_content,
    sanitize_event,
    sanitize_events,
)


class ForgeTest(unittest.TestCase):
    def test_sanitize_content_keeps_only_resume_safe_blocks(self):
        self.assertEqual(sanitize_content("user", "hello"), "hello")
        self.assertIsNone(sanitize_content("user", "  "))
        self.assertEqual(
            sanitize_content(
                "assistant",
                [
                    {"type": "text", "text": "ok"},
                    {"type": "tool_use", "name": "read"},
                    {"type": "thinking", "thinking": "..."},
                ],
            ),
            [{"type": "text", "text": "ok"}, {"type": "thinking", "thinking": "..."}],
        )

    def test_sanitize_event_removes_runtime_fields_and_meta(self):
        event = {
            "type": "assistant",
            "requestId": "private-id",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "reply"}, {"type": "tool_use", "name": "x"}],
                "usage": {"tokens": 1},
                "diagnostics": {"trace": "x"},
            },
        }

        clean = sanitize_event(event)

        self.assertNotIn("requestId", clean)
        self.assertNotIn("usage", clean["message"])
        self.assertNotIn("diagnostics", clean["message"])
        self.assertEqual(clean["message"]["content"], [{"type": "text", "text": "reply"}])
        self.assertIsNone(sanitize_event({"type": "user", "isMeta": True, "message": {"role": "user", "content": "hidden"}}))

    def test_sanitize_events_filters_runtime_noise_turn_and_reply(self):
        rows = [
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "FORGE_CONTEXT_SUMMARY:\nhidden"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "also hidden"}]}},
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "keep me"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "kept reply"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "API Error: hidden"}]}},
        ]

        cleaned = sanitize_events(rows)

        self.assertEqual([event_text(event) for event in cleaned], ["keep me", "kept reply"])

    def test_filter_runtime_noise_turns_resumes_at_next_user(self):
        rows = [
            {"type": "user", "message": {"role": "user", "content": "FORGE_RESUME_READY_hidden"}},
            {"type": "assistant", "message": {"role": "assistant", "content": "hidden"}},
            {"type": "user", "message": {"role": "user", "content": "visible"}},
        ]

        self.assertEqual([event_text(event) for event in filter_runtime_noise_turns(rows)], ["visible"])

    def test_real_user_and_token_estimate(self):
        user = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "hello"}]}}
        assistant = {"type": "assistant", "message": {"role": "assistant", "content": "hello"}}

        self.assertEqual(content_blocks(user["message"]["content"]), ["text"])
        self.assertTrue(is_real_user(user))
        self.assertFalse(is_real_user(assistant))
        self.assertGreaterEqual(estimate_tokens(user), 1)


if __name__ == "__main__":
    unittest.main()
