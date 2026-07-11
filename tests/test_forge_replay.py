import unittest

from bridge.forge_replay import replay_payload


def user(content, **extra):
    event = {"type": "user", "message": {"role": "user", "content": content}}
    event.update(extra)
    return event


def assistant(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


class ForgeReplayTest(unittest.TestCase):
    def test_replay_payload_collects_real_user_text(self):
        rows = [
            assistant("ignored"),
            user([{"type": "text", "text": " replay me "}], timestamp="t1"),
            user([{"type": "tool_result", "tool_use_id": "x", "content": "tool only"}], timestamp="t2"),
        ]

        payload = replay_payload(rows, "sid", created_at="now")

        self.assertEqual(
            payload,
            {
                "new_sid": "sid",
                "created_at": "now",
                "messages": [{"timestamp": "t1", "text": " replay me "}],
            },
        )

    def test_replay_payload_returns_none_without_real_user_text(self):
        rows = [assistant("ignored"), user([{"type": "tool_result", "tool_use_id": "x", "content": "tool"}])]

        self.assertIsNone(replay_payload(rows, "sid", created_at="now"))

    def test_replay_payload_handles_string_content(self):
        payload = replay_payload([user("plain text")], "sid", created_at="now")

        self.assertEqual(payload["messages"], [{"timestamp": "", "text": "plain text"}])


if __name__ == "__main__":
    unittest.main()
