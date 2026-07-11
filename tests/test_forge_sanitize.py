import unittest

from bridge.forge_sanitize import (
    clean_event,
    clean_events,
    content_text,
    filter_noise_turns_tool_aware,
    filter_runtime_noise_turns,
    has_summary_flag,
    is_runtime_noise,
    sanitize_content,
    sanitize_event,
    sanitize_events,
)


ASSISTANT_BLOCKS = {"thinking", "redacted_thinking", "text"}
USER_BLOCKS = {"text"}


def user(text, **extra):
    event = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}
    event.update(extra)
    return event


def assistant(text, **extra):
    event = {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}
    event.update(extra)
    return event


class ForgeSanitizeTest(unittest.TestCase):
    def test_sanitize_content_keeps_only_allowed_blocks(self):
        self.assertEqual(sanitize_content("user", "hello", ASSISTANT_BLOCKS, USER_BLOCKS), "hello")
        self.assertIsNone(sanitize_content("user", "  ", ASSISTANT_BLOCKS, USER_BLOCKS))
        self.assertEqual(
            sanitize_content(
                "assistant",
                [
                    {"type": "text", "text": "reply"},
                    {"type": "tool_use", "name": "ignored"},
                    {"type": "thinking", "thinking": "..."},
                ],
                ASSISTANT_BLOCKS,
                USER_BLOCKS,
            ),
            [{"type": "text", "text": "reply"}, {"type": "thinking", "thinking": "..."}],
        )

    def test_content_text_and_noise_detection_use_injected_markers(self):
        content = [{"type": "text", "text": "hello"}, {"type": "tool_use", "name": "ignored"}]

        self.assertEqual(content_text(content), "hello")
        self.assertTrue(is_runtime_noise("assistant", "API Error: overloaded", ("API Error:",), ()))
        self.assertTrue(is_runtime_noise("user", "FORGE_CONTEXT_SUMMARY:\nhidden", (), ("FORGE_CONTEXT_SUMMARY:",)))
        self.assertFalse(is_runtime_noise("user", "normal", (), ("FORGE_CONTEXT_SUMMARY:",)))
        # A real message that merely mentions the token (not as its opening line)
        # must survive — the marker is not a free substring filter.
        self.assertFalse(
            is_runtime_noise(
                "user",
                "Here is my report.\nI reworked how FORGE_CONTEXT_SUMMARY: is handled.",
                (),
                ("FORGE_CONTEXT_SUMMARY:",),
            )
        )

    def test_sanitize_event_removes_runtime_fields_and_meta(self):
        event = assistant("reply", requestId="rid")
        event["message"]["content"].append({"type": "tool_use", "name": "ignored"})
        event["message"]["usage"] = {"tokens": 1}
        event["message"]["diagnostics"] = {"trace": "x"}

        clean = sanitize_event(event, ASSISTANT_BLOCKS, USER_BLOCKS, ("API Error:",))

        self.assertNotIn("requestId", clean)
        self.assertNotIn("usage", clean["message"])
        self.assertNotIn("diagnostics", clean["message"])
        self.assertEqual(clean["message"]["content"], [{"type": "text", "text": "reply"}])
        self.assertIsNone(sanitize_event(user("hidden", isMeta=True), ASSISTANT_BLOCKS, USER_BLOCKS))
        self.assertIsNone(sanitize_event(user("summary", forgeSummary=True), ASSISTANT_BLOCKS, USER_BLOCKS))

    def test_sanitize_event_keeps_channel_meta_messages(self):
        channel = {
            "type": "user",
            "isMeta": True,
            "message": {"role": "user", "content": '<channel source="telegram">hello</channel>'},
        }

        clean = sanitize_event(channel, ASSISTANT_BLOCKS, USER_BLOCKS)

        self.assertEqual(clean["message"]["content"], '<channel source="telegram">hello</channel>')

    def test_sanitize_events_filters_runtime_noise_turn_and_reply(self):
        rows = [
            user("FORGE_CONTEXT_SUMMARY:\nhidden"),
            assistant("hidden reply"),
            user("keep me", requestId="rid"),
            assistant("kept reply"),
            assistant("API Error: hidden"),
        ]

        cleaned = sanitize_events(rows, ASSISTANT_BLOCKS, USER_BLOCKS, ("API Error:",), ("FORGE_CONTEXT_SUMMARY:",))

        self.assertEqual([content_text(event["message"]["content"]) for event in cleaned], ["keep me", "kept reply"])
        self.assertNotIn("requestId", cleaned[0])

    def test_filter_runtime_noise_turns_resumes_at_next_user(self):
        rows = [user("FORGE_RESUME_READY_hidden"), assistant("hidden"), user("visible")]

        cleaned = filter_runtime_noise_turns(rows, user_markers=("FORGE_RESUME_READY_",))

        self.assertEqual([content_text(event["message"]["content"]) for event in cleaned], ["visible"])

    def test_filter_noise_turns_tool_aware_keeps_tool_results_inside_skipped_turn(self):
        rows = [
            user("FORGE_RESUME_READY_hidden"),
            {
                "type": "user",
                "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "hidden"}]},
            },
            assistant("hidden reply"),
            user("visible"),
        ]

        cleaned = filter_noise_turns_tool_aware(rows, user_markers=("FORGE_RESUME_READY_",))

        self.assertEqual([content_text(event["message"]["content"]) for event in cleaned], ["visible"])

    def test_clean_event_preserves_tool_blocks_and_strips_runtime_fields(self):
        event = assistant("reply", requestId="rid")
        event["message"]["content"].append({"type": "tool_use", "id": "tool", "name": "run"})
        event["message"]["usage"] = {"tokens": 1}
        event["message"]["diagnostics"] = {"trace": "x"}

        clean = clean_event(event)

        self.assertIn({"type": "tool_use", "id": "tool", "name": "run"}, clean["message"]["content"])
        self.assertNotIn("usage", clean["message"])
        self.assertNotIn("diagnostics", clean["message"])
        self.assertIn("requestId", clean)

    def test_clean_events_filters_previous_forge_summary_and_noise(self):
        rows = [
            user("old summary", forgeSummary=True),
            user("FORGE_CONTEXT_SUMMARY:\nhidden"),
            assistant("hidden reply"),
            user("visible"),
        ]

        cleaned = clean_events(rows, user_markers=("FORGE_CONTEXT_SUMMARY:",))

        self.assertEqual([content_text(event["message"]["content"]) for event in cleaned], ["visible"])

    def test_summary_flag_fields_are_configurable_for_instances(self):
        event = user("summary", instanceSummary=True)

        self.assertTrue(has_summary_flag(event, ("instanceSummary",)))
        self.assertIsNone(clean_event(event, ("instanceSummary",)))
        self.assertIsNone(sanitize_event(event, ASSISTANT_BLOCKS, USER_BLOCKS, summary_flag_fields=("instanceSummary",)))


if __name__ == "__main__":
    unittest.main()
