import unittest

from bridge.forge import (
    content_blocks,
    choose_kept,
    close_at_final_assistant,
    estimate_tokens,
    event_text,
    filter_runtime_noise_turns,
    forge_events,
    is_real_user,
    sanitize_content,
    sanitize_event,
    sanitize_events,
    validate_chain,
)


def user(text):
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def assistant(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


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
        user_event = user("hello")
        assistant_event = {"type": "assistant", "message": {"role": "assistant", "content": "hello"}}

        self.assertEqual(content_blocks(user_event["message"]["content"]), ["text"])
        self.assertTrue(is_real_user(user_event))
        self.assertFalse(is_real_user(assistant_event))
        self.assertGreaterEqual(estimate_tokens(user_event), 1)

    def test_choose_kept_starts_at_first_real_user_after_cut(self):
        events = [user("old"), assistant("old reply"), user("new"), assistant("new reply")]
        selection = choose_kept(events, 2, token_estimator=lambda event: 1)

        self.assertEqual([event_text(event) for event in selection.kept], ["new", "new reply"])
        self.assertEqual(selection.raw_cut_index, 2)
        self.assertEqual(selection.keep_start_index, 2)
        self.assertEqual(selection.estimated_tokens_scanned, 3)

    def test_choose_kept_raises_when_tail_has_no_real_user(self):
        events = [user("old"), assistant("tail")]

        with self.assertRaisesRegex(ValueError, "no real user"):
            choose_kept(events, 1, token_estimator=lambda event: 1)

    def test_close_at_final_assistant_trims_open_tail(self):
        events = [user("first"), assistant("reply"), user("open tail")]
        selection = close_at_final_assistant(events, allow_open_turn=True)

        self.assertEqual([event_text(event) for event in selection.kept], ["first", "reply"])
        self.assertEqual(selection.terminal_type_before_trim, "user")
        self.assertEqual(selection.terminal_type, "assistant")
        self.assertEqual(len(selection.warnings), 2)
        self.assertIn("trimmed 1 trailing", selection.warnings[0])

    def test_close_at_final_assistant_requires_assistant(self):
        with self.assertRaisesRegex(ValueError, "no assistant"):
            close_at_final_assistant([user("only user")])

    def test_forge_events_rewrites_session_and_parent_chain(self):
        events = [
            {**user("first"), "uuid": "old-1", "sessionId": "old-session", "parentUuid": "old-parent"},
            {**assistant("reply"), "uuid": "old-2", "sessionId": "old-session", "parentUuid": "old-1"},
        ]
        ids = iter(["new-1", "new-2"])

        forged, uuid_map = forge_events(events, "new-session", uuid_factory=lambda: next(ids))

        self.assertEqual(uuid_map, {"old-1": "new-1", "old-2": "new-2"})
        self.assertEqual([event["uuid"] for event in forged], ["new-1", "new-2"])
        self.assertEqual([event["sessionId"] for event in forged], ["new-session", "new-session"])
        self.assertEqual([event["parentUuid"] for event in forged], [None, "new-1"])
        validate_chain(forged)

    def test_forge_events_can_preserve_existing_uuids(self):
        events = [{**user("first"), "uuid": "old-1"}, {**assistant("reply"), "uuid": "old-2"}]

        forged, uuid_map = forge_events(events, "new-session", rewrite_event_uuids=False)

        self.assertEqual(uuid_map, {})
        self.assertEqual([event["uuid"] for event in forged], ["old-1", "old-2"])
        self.assertEqual([event["parentUuid"] for event in forged], [None, "old-1"])

    def test_validate_chain_rejects_duplicate_or_missing_parents(self):
        with self.assertRaisesRegex(ValueError, "duplicate uuid"):
            validate_chain([{"uuid": "same", "parentUuid": None}, {"uuid": "same", "parentUuid": "same"}])

        with self.assertRaisesRegex(ValueError, "missing parents"):
            validate_chain([{"uuid": "child", "parentUuid": "missing"}])


if __name__ == "__main__":
    unittest.main()
