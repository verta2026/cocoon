import unittest

from bridge.forge_plan_core import (
    choose_kept,
    content_blocks,
    estimate_tokens,
    forge_events,
    is_channel_message,
    is_real_user,
    repair_tool_pairs,
    role_of,
    validate_chain,
)


def user(text, uuid="u"):
    return {"type": "user", "uuid": uuid, "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def assistant(text, uuid="a"):
    return {
        "type": "assistant",
        "uuid": uuid,
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


class ForgePlanCoreTest(unittest.TestCase):
    def test_role_blocks_and_real_user_detection(self):
        event = user("hello")
        channel = {"type": "user", "isMeta": True, "message": {"role": "user", "content": '<channel source="chat">hi'}}

        self.assertEqual(role_of(event), "user")
        self.assertEqual(content_blocks(event["message"]["content"]), ["text"])
        self.assertEqual(content_blocks("plain"), ["string"])
        self.assertTrue(is_real_user(event))
        self.assertTrue(is_channel_message(channel))
        self.assertTrue(is_real_user(channel))
        self.assertFalse(is_real_user({"type": "user", "isMeta": True, "message": {"role": "user", "content": "hidden"}}))
        self.assertFalse(is_real_user(assistant("reply")))

    def test_estimate_tokens_and_choose_kept(self):
        events = [user("old", "u1"), assistant("old reply", "a1"), user("new", "u2"), assistant("new reply", "a2")]
        retain_tokens = estimate_tokens(events[2]) + estimate_tokens(events[3])

        kept, raw_cut, keep_start, scanned = choose_kept(events, retain_tokens)

        self.assertEqual([event["uuid"] for event in kept], ["u2", "a2"])
        self.assertEqual(raw_cut, 2)
        self.assertEqual(keep_start, 2)
        self.assertGreater(scanned, retain_tokens)
        self.assertGreaterEqual(estimate_tokens(events[0]), 1)

    def test_choose_kept_returns_empty_when_no_boundary_after_cut(self):
        kept, raw_cut, keep_start, scanned = choose_kept([user("old"), assistant("tail")], 1)

        self.assertEqual(kept, [])
        self.assertEqual(keep_start, 2)
        self.assertGreaterEqual(raw_cut, 1)
        self.assertGreater(scanned, 0)

    def test_choose_kept_can_grow_backward_to_real_user(self):
        events = [user("old", "u1"), assistant("tail" * 80, "a1")]
        limit = sum(estimate_tokens(event) for event in events) + 5

        kept, _, keep_start, _ = choose_kept(events, 1, grow_backward_limit=limit)

        self.assertEqual(kept, events)
        self.assertEqual(keep_start, 0)

    def test_repair_tool_pairs_drops_orphan_tool_blocks(self):
        events = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "working"},
                        {"type": "tool_use", "id": "missing", "name": "x"},
                        {"type": "tool_use", "id": "paired", "name": "x"},
                    ],
                },
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": "orphan", "content": "late"},
                        {"type": "tool_result", "tool_use_id": "paired", "content": "ok"},
                    ],
                },
            },
        ]

        repaired, repairs = repair_tool_pairs(events)

        self.assertEqual(repairs, 2)
        self.assertEqual(
            repaired[0]["message"]["content"],
            [{"type": "text", "text": "working"}, {"type": "tool_use", "id": "paired", "name": "x"}],
        )
        self.assertEqual(repaired[1]["message"]["content"], [{"type": "tool_result", "tool_use_id": "paired", "content": "ok"}])
        self.assertEqual(len(events[0]["message"]["content"]), 3)

    def test_forge_events_rewrites_session_and_parent_chain(self):
        events = [user("first", "old-1"), assistant("reply", "old-2")]
        ids = iter(["new-1", "new-2"])

        forged, uuid_map = forge_events(events, "new-session", uuid_factory=lambda: next(ids))

        self.assertEqual(uuid_map, {"old-1": "new-1", "old-2": "new-2"})
        self.assertEqual([event["uuid"] for event in forged], ["new-1", "new-2"])
        self.assertEqual([event["sessionId"] for event in forged], ["new-session", "new-session"])
        self.assertEqual([event["parentUuid"] for event in forged], [None, "new-1"])
        validate_chain(forged)

    def test_forge_events_can_preserve_existing_uuids(self):
        events = [user("first", "old-1"), assistant("reply", "old-2")]

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
