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
    inject_summary_event,
    is_runtime_noise,
    prepare_summary,
    sha_text,
    synthetic_summary_event,
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

    def test_long_handoff_block_is_filtered_but_quote_survives(self):
        # A real FORGE_CONTEXT_SUMMARY handoff block is hundreds of chars and
        # *begins* with the marker — it must be filtered regardless of length
        # (the old 200-char cap let it leak into the sanitized transcript).
        long_block = FORGE_SUMMARY_MARKER + "\n" + ("hidden internal handoff. " * 40)
        self.assertGreater(len(long_block), 200)
        self.assertTrue(is_runtime_noise("user", long_block))

        # A genuine chat message that merely *mentions* the marker mid-sentence
        # must survive — anchoring to the start of the line is what distinguishes
        # the two, so a long quote is never eaten.
        quote = "I traced why the " + FORGE_SUMMARY_MARKER + " block leaked. " * 20
        self.assertGreater(len(quote), 200)
        self.assertFalse(is_runtime_noise("user", quote))

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

    def test_synthetic_summary_event_uses_template_without_private_runtime_fields(self):
        template = {
            "type": "user",
            "uuid": "old-id",
            "requestId": "private-request",
            "timestamp": "old-time",
            "message": {"role": "user", "content": "old"},
        }

        event = synthetic_summary_event("summary", template, timestamp="new-time")

        text = event["message"]["content"][0]["text"]
        self.assertEqual(event["type"], "user")
        self.assertFalse(event["isMeta"])
        self.assertEqual(event["timestamp"], "new-time")
        self.assertEqual(event["uuid"], "old-id")
        self.assertNotIn("requestId", event)
        self.assertIn(FORGE_SUMMARY_MARKER, text)
        self.assertIn("summary", text)

    def test_inject_summary_event_prepends_only_when_summary_exists(self):
        kept = [{"type": "assistant", "message": {"role": "assistant", "content": "reply"}}]

        unchanged, injected = inject_summary_event(kept, "")
        changed, did_inject = inject_summary_event(kept, "summary", timestamp="now")

        self.assertIs(unchanged, kept)
        self.assertFalse(injected)
        self.assertTrue(did_inject)
        self.assertEqual(len(changed), 2)
        self.assertEqual(changed[0]["timestamp"], "now")
        self.assertIs(changed[1], kept[0])


if __name__ == "__main__":
    unittest.main()
