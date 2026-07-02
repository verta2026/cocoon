import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge.reload_replay import current_resume_sid, maybe_replay_forge_tail


class ReloadReplayTest(unittest.TestCase):
    def test_current_resume_sid_chooses_single_running_sid(self):
        result = type(
            "Result",
            (),
            {"stdout": "claude --resume 11111111-1111-1111-1111-111111111111\nother --resume ignored\n"},
        )()

        with tempfile.TemporaryDirectory() as tmp, patch("bridge.reload_replay.subprocess.run", return_value=result):
            self.assertEqual(current_resume_sid(Path(tmp)), "11111111-1111-1111-1111-111111111111")

    def test_current_resume_sid_uses_newest_jsonl_when_multiple_are_running(self):
        result = type(
            "Result",
            (),
            {
                "stdout": (
                    "claude --resume 11111111-1111-1111-1111-111111111111\n"
                    "claude --resume 22222222-2222-2222-2222-222222222222\n"
                )
            },
        )()

        with tempfile.TemporaryDirectory() as tmp, patch("bridge.reload_replay.subprocess.run", return_value=result):
            root = Path(tmp)
            first = root / "11111111-1111-1111-1111-111111111111.jsonl"
            second = root / "22222222-2222-2222-2222-222222222222.jsonl"
            first.write_text("{}", encoding="utf-8")
            second.write_text("{}", encoding="utf-8")
            old = time.time() - 100
            os.utime(first, (old, old))
            os.utime(second, None)

            self.assertEqual(current_resume_sid(root), "22222222-2222-2222-2222-222222222222")

    def test_maybe_replay_forge_tail_sends_matching_pending_messages_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            replay_file = Path(tmp) / "replay.json"
            replay_file.write_text(
                json.dumps(
                    {
                        "new_sid": "sid-1",
                        "messages": [{"text": " hello "}, {"text": ""}, {"text": "world"}],
                    }
                ),
                encoding="utf-8",
            )
            sent = []
            logs = []

            result = maybe_replay_forge_tail(
                replay_file,
                lambda: "sid-1",
                sent.append,
                logs.append,
                sleep_func=lambda seconds: None,
            )

            self.assertEqual(result, "forge-tail-replay:2")
            self.assertEqual(sent, [" hello ", "world"])
            self.assertEqual(logs, ["replayed 2 message(s) trimmed at the last swap into sid-1"])
            self.assertFalse(replay_file.exists())

    def test_maybe_replay_forge_tail_keeps_fresh_mismatched_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            replay_file = Path(tmp) / "replay.json"
            replay_file.write_text(json.dumps({"new_sid": "sid-old", "messages": [{"text": "hello"}]}), encoding="utf-8")

            result = maybe_replay_forge_tail(
                replay_file,
                lambda: "sid-new",
                lambda text: None,
                lambda text: None,
                stale_seconds=3600,
                sleep_func=lambda seconds: None,
            )

            self.assertEqual(result, "")
            self.assertTrue(replay_file.exists())

    def test_maybe_replay_forge_tail_drops_stale_mismatched_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            replay_file = Path(tmp) / "replay.json"
            replay_file.write_text(json.dumps({"new_sid": "sid-old", "messages": [{"text": "hello"}]}), encoding="utf-8")
            old = time.time() - 7200
            os.utime(replay_file, (old, old))
            logs = []

            result = maybe_replay_forge_tail(
                replay_file,
                lambda: "sid-new",
                lambda text: None,
                logs.append,
                stale_seconds=60,
                sleep_func=lambda seconds: None,
            )

            self.assertEqual(result, "")
            self.assertEqual(logs, ["replay dropped stale pending file (for sid sid-old)"])
            self.assertFalse(replay_file.exists())

    def test_maybe_replay_forge_tail_drops_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            replay_file = Path(tmp) / "replay.json"
            replay_file.write_text("{bad", encoding="utf-8")

            result = maybe_replay_forge_tail(
                replay_file,
                lambda: "sid",
                lambda text: None,
                lambda text: None,
                sleep_func=lambda seconds: None,
            )

            self.assertEqual(result, "")
            self.assertFalse(replay_file.exists())


if __name__ == "__main__":
    unittest.main()
