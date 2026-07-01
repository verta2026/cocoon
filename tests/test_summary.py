import unittest

from bridge.summary import (
    FORGE_SUMMARY_MARKER,
    SummaryInput,
    build_summary_messages,
    call_summary_provider,
    clamp_middle,
    content_text,
    event_speaker,
    extract_summary_marker,
    format_events_for_summary,
    prepare_summary,
    sha_text,
)


class SummaryTest(unittest.TestCase):
    def test_extract_summary_marker_accepts_marked_or_plain_text(self):
        self.assertEqual(extract_summary_marker(f"note\n{FORGE_SUMMARY_MARKER}\nkept"), "kept")
        self.assertEqual(extract_summary_marker("plain summary"), "plain summary")

    def test_build_summary_messages_uses_generic_prompt(self):
        messages = build_summary_messages("old", "raw")

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn(FORGE_SUMMARY_MARKER, messages[0]["content"])
        self.assertIn("old", messages[1]["content"])
        self.assertIn("raw", messages[1]["content"])
        self.assertNotIn("DeepSeek", messages[0]["content"])

    def test_clamp_middle_preserves_edges(self):
        text = "0123456789abcdef"
        clamped = clamp_middle(text, 8)

        self.assertTrue(clamped.startswith("0123"))
        self.assertTrue(clamped.endswith("cdef"))
        self.assertIn("omitted", clamped)

    def test_content_text_reads_string_and_text_blocks(self):
        self.assertEqual(content_text("hello"), "hello")
        self.assertEqual(
            content_text([{"type": "text", "text": "hello"}, {"type": "tool_use", "name": "read"}]),
            "hello",
        )

    def test_format_events_for_summary_uses_generic_speakers_and_filters_noise(self):
        events = [
            {
                "type": "user",
                "timestamp": "2026-06-30T00:00:00Z",
                "message": {"role": "user", "content": [{"type": "text", "text": "first"}]},
            },
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "reply"}]},
            },
            {
                "type": "user",
                "message": {"role": "user", "content": [{"type": "text", "text": "FORGE_CONTEXT_SUMMARY:\nhidden"}]},
            },
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "API Error: hidden"}]},
            },
        ]

        formatted = format_events_for_summary(events, 500)

        self.assertIn("[2026-06-30T00:00:00Z] user:\nfirst", formatted)
        self.assertIn("assistant:\nreply", formatted)
        self.assertNotIn("hidden", formatted)
        self.assertNotIn("Bound", formatted)
        self.assertNotIn("Leta", formatted)

    def test_channel_event_speaker_is_generic(self):
        event = {"message": {"role": "user", "content": "<channel source=\"chat\">hello</channel>"}}

        self.assertEqual(event_speaker(event), "channel")

    def test_provider_boundary_is_disabled_by_default(self):
        self.assertEqual(call_summary_provider("none", "old", "raw"), ("", "provider-disabled"))
        self.assertEqual(call_summary_provider("deepseek", "old", "raw"), ("", "unsupported-provider:deepseek"))

    def test_prepare_summary_reuses_matching_meta(self):
        previous = "old summary"
        dropped = "raw text"
        result = prepare_summary(
            SummaryInput(previous, dropped, source_id="session-a", provider="custom", write=True),
            meta={
                "source": "session-a",
                "dropped_hash": sha_text(dropped),
                "previous_hash": sha_text(previous),
            },
            call_provider=lambda old, raw: ("new summary", "updated"),
        )

        self.assertEqual(result.summary, previous)
        self.assertEqual(result.info["status"], "reused")
        self.assertFalse(result.info["write_summary"])

    def test_prepare_summary_uses_injected_provider(self):
        result = prepare_summary(
            SummaryInput("old", "raw", source_id="session-a", provider="custom", write=True),
            call_provider=lambda old, raw: (f"{FORGE_SUMMARY_MARKER}\nnew summary", "updated"),
        )

        self.assertEqual(result.summary, "new summary")
        self.assertEqual(result.info["status"], "updated")
        self.assertTrue(result.info["write_summary"])


if __name__ == "__main__":
    unittest.main()
