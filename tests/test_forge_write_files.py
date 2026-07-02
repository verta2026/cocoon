import json
import tempfile
import unittest
from pathlib import Path

from bridge.forge_write_files import (
    build_manifest_payload,
    build_summary_meta_payload,
    write_json_atomic,
    write_jsonl_atomic,
)


class ForgeWriteFilesTest(unittest.TestCase):
    def test_write_jsonl_atomic_writes_compact_jsonl_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "project" / "session.jsonl"
            events = [
                {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "hello"}]}},
                {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "reply"}]}},
            ]

            result = write_jsonl_atomic(dest, events)

            self.assertEqual(result, dest)
            text = dest.read_text(encoding="utf-8")
            self.assertEqual(text.count("\n"), 2)
            self.assertIn('"content":[{"type":"text","text":"hello"}]', text)
            self.assertFalse(dest.with_name(dest.name + ".tmp").exists())

            with self.assertRaises(FileExistsError):
                write_jsonl_atomic(dest, events)

    def test_write_json_atomic_writes_pretty_json_with_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "manifest" / "sid.manifest.json"

            write_json_atomic(dest, {"new_sid": "sid", "written": True})

            text = dest.read_text(encoding="utf-8")
            self.assertTrue(text.endswith("\n"))
            self.assertIn('"new_sid": "sid"', text)
            self.assertIn('"written": true', text)
            self.assertFalse(dest.with_name(dest.name + ".tmp").exists())

    def test_build_summary_meta_payload_uses_public_summary_fields(self):
        payload = build_summary_meta_payload(
            source="source.jsonl",
            new_session_id="sid",
            summary_text="summary",
            summary_info={
                "dropped_events": 2,
                "dropped_chars": 40,
                "dropped_hash": "abc",
                "previous_hash": "prev",
                "status": "updated",
                "provider": "deepseek",
                "prompt_file": "prompt.md",
            },
            updated_at="2026-07-01T00:00:00Z",
            summary_hash="hash",
        )

        self.assertEqual(payload["updated_at"], "2026-07-01T00:00:00Z")
        self.assertEqual(payload["source"], "source.jsonl")
        self.assertEqual(payload["new_sid"], "sid")
        self.assertEqual(payload["dropped_events"], 2)
        self.assertEqual(payload["summary_hash"], "hash")
        self.assertEqual(payload["summary_chars"], 7)
        self.assertEqual(payload["provider"], "deepseek")
        self.assertEqual(payload["prompt_file"], "prompt.md")

    def test_build_manifest_payload_adds_created_at_without_mutating_summary(self):
        summary = {"new_sid": "sid", "written": True}

        payload = build_manifest_payload(summary, created_at="now")

        self.assertEqual(payload, {"new_sid": "sid", "written": True, "created_at": "now"})
        self.assertNotIn("created_at", summary)


if __name__ == "__main__":
    unittest.main()
