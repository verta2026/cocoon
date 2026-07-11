import unittest

from bridge.forge_summary_format import clamp_middle, event_speaker, event_timestamp, format_events_for_summary


def user(text, **extra):
    event = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}
    event.update(extra)
    return event


def assistant(text, **extra):
    event = {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}
    event.update(extra)
    return event


class ForgeSummaryFormatTest(unittest.TestCase):
    def test_event_timestamp_and_speaker_use_injected_names(self):
        event = user("hello", timestamp="2026-07-01T00:00:00Z")
        channel = {"type": "user", "message": {"role": "user", "content": '<channel source="chat">hello</channel>'}}

        self.assertEqual(event_timestamp(event), "2026-07-01T00:00:00Z")
        self.assertEqual(event_speaker(event, user_name="Alice"), "Alice")
        self.assertEqual(event_speaker(assistant("reply"), assistant_name="Robin"), "Robin")
        self.assertEqual(event_speaker(channel, channel_name="Channel/User"), "Channel/User")
        self.assertEqual(event_speaker({"type": "tool", "message": {"role": "tool"}}), "tool")

    def test_clamp_middle_preserves_edges_with_custom_template(self):
        text = "0123456789abcdef"

        clamped = clamp_middle(text, 8, "[cut {omitted}]")

        self.assertTrue(clamped.startswith("0123"))
        self.assertTrue(clamped.endswith("cdef"))
        self.assertIn("[cut 8]", clamped)
        self.assertEqual(clamp_middle(text, 0), text)

    def test_format_events_for_summary_uses_names_and_filters_noise(self):
        events = [
            user("hello", timestamp="2026-07-01T00:00:00Z"),
            assistant("reply"),
            user("FORGE_CONTEXT_SUMMARY:\nhidden"),
            assistant("API Error: hidden"),
        ]

        formatted = format_events_for_summary(
            events,
            500,
            assistant_name="Robin",
            user_name="Alice",
            assistant_prefixes=("API Error:",),
            user_markers=("FORGE_CONTEXT_SUMMARY:",),
        )

        self.assertIn("[2026-07-01T00:00:00Z] Alice:\nhello", formatted)
        self.assertIn("Robin:\nreply", formatted)
        self.assertNotIn("hidden", formatted)

    def test_format_events_for_summary_skips_empty_text_and_clamps(self):
        events = [user(""), user("0123456789abcdef")]

        formatted = format_events_for_summary(events, 8, user_name="User", omitted_template="[cut {omitted}]")

        self.assertIn("[cut", formatted)
        self.assertNotIn("User:\n\n", formatted)


if __name__ == "__main__":
    unittest.main()
