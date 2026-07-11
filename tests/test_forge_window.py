import unittest

from bridge.forge_window import build_window, window_is_viable


ASSISTANT_BLOCKS = {"thinking", "redacted_thinking", "text"}
USER_BLOCKS = {"text"}


def user(text, **extra):
    event = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}
    event.update(extra)
    return event


def assistant(content, **extra):
    event = {"type": "assistant", "message": {"role": "assistant", "content": content}}
    event.update(extra)
    return event


class ForgeWindowTest(unittest.TestCase):
    def test_build_window_splits_raw_dialogue_and_dropped_zones(self):
        rows = [
            user("old"),
            assistant([{"type": "text", "text": "old reply"}]),
            user("new"),
            assistant([{"type": "text", "text": "new reply"}, {"type": "tool_use", "id": "tool"}]),
        ]

        window = build_window(rows, 20, 500, ASSISTANT_BLOCKS, USER_BLOCKS)

        self.assertEqual(window["clean_events"], 4)
        self.assertEqual(window["raw_zone_events"], 0)
        self.assertEqual(window["dialogue_zone_events"], 4)
        self.assertEqual(window["dropped"], [])
        self.assertEqual(window["tool_pair_repairs"], 0)
        self.assertTrue(window_is_viable(window))
        self.assertNotIn({"type": "tool_use", "id": "tool"}, window["kept"][-1]["message"]["content"])

    def test_build_window_repairs_orphan_tool_use_in_raw_zone(self):
        rows = [
            user("run"),
            assistant([{"type": "text", "text": "working"}, {"type": "tool_use", "id": "missing"}]),
        ]

        window = build_window(rows, 500, 1, ASSISTANT_BLOCKS, USER_BLOCKS)

        self.assertEqual(window["raw_zone_events"], 2)
        self.assertEqual(window["tool_pair_repairs"], 1)
        self.assertEqual(window["kept"][-1]["message"]["content"], [{"type": "text", "text": "working"}])

    def test_build_window_filters_runtime_noise_before_zoning(self):
        rows = [
            user("FORGE_CONTEXT_SUMMARY:\nhidden"),
            assistant([{"type": "text", "text": "hidden reply"}]),
            user("visible"),
            assistant([{"type": "text", "text": "reply"}]),
        ]

        window = build_window(
            rows,
            500,
            500,
            ASSISTANT_BLOCKS,
            USER_BLOCKS,
            user_markers=("FORGE_CONTEXT_SUMMARY:",),
        )

        self.assertEqual(window["clean_events"], 2)
        self.assertEqual([event["message"]["content"][0]["text"] for event in window["kept"]], ["visible", "reply"])

    def test_window_is_viable_requires_user_and_text_assistant(self):
        self.assertFalse(window_is_viable({"kept": [user("only")]}))
        self.assertFalse(window_is_viable({"kept": [assistant([{"type": "text", "text": "only"}])]}))
        self.assertFalse(window_is_viable({"kept": [user("x"), assistant([{"type": "tool_use", "id": "x"}])]}))


if __name__ == "__main__":
    unittest.main()
