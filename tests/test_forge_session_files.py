import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from bridge.forge_session_files import (
    iter_project_jsonl,
    latest_jsonl,
    load_jsonl,
    session_last_timestamp,
    session_sort_key,
)


class ForgeSessionFilesTest(unittest.TestCase):
    def test_load_jsonl_reads_non_empty_rows_and_reports_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text(
                json.dumps({"type": "user"}) + "\n\n" + json.dumps({"type": "assistant"}) + "\n",
                encoding="utf-8",
            )

            self.assertEqual([row["type"] for row in load_jsonl(path)], ["user", "assistant"])

            bad = Path(tmp) / "bad.jsonl"
            bad.write_text("{}\n{bad}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "bad json"):
                load_jsonl(bad)

    def test_iter_project_jsonl_only_returns_top_level_jsonl_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.jsonl").write_text("{}", encoding="utf-8")
            (root / "b.txt").write_text("{}", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "c.jsonl").write_text("{}", encoding="utf-8")

            self.assertEqual([path.name for path in iter_project_jsonl(root)], ["a.jsonl"])

    def test_session_last_timestamp_uses_latest_timestamp_and_skips_bad_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text(
                "{bad}\n"
                + json.dumps({"timestamp": "2026-07-01T00:00:00Z"})
                + "\n"
                + json.dumps({"created_at": "2026-07-01T00:00:02Z"})
                + "\n",
                encoding="utf-8",
            )

            self.assertEqual(session_last_timestamp(path), "2026-07-01T00:00:02Z")
            self.assertEqual(session_last_timestamp(Path(tmp) / "missing.jsonl"), "")

    def test_latest_jsonl_prefers_timestamp_then_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old.jsonl"
            newer = root / "newer.jsonl"
            old.write_text(json.dumps({"timestamp": "2026-07-01T00:00:00Z"}) + "\n", encoding="utf-8")
            newer.write_text(json.dumps({"timestamp": "2026-07-01T00:00:02Z"}) + "\n", encoding="utf-8")

            self.assertEqual(latest_jsonl(root), newer)
            self.assertGreater(session_sort_key(newer), session_sort_key(old))

    def test_latest_jsonl_falls_back_to_mtime_when_timestamps_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.jsonl"
            second = root / "second.jsonl"
            first.write_text("{}", encoding="utf-8")
            second.write_text("{}", encoding="utf-8")
            old_time = time.time() - 60
            os.utime(first, (old_time, old_time))

            self.assertEqual(latest_jsonl(root), second)

            empty = root / "empty"
            empty.mkdir()
            with self.assertRaisesRegex(ValueError, "no jsonl files"):
                latest_jsonl(empty)


if __name__ == "__main__":
    unittest.main()
