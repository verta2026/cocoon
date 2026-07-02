import json
import tempfile
import unittest
from pathlib import Path

from bridge.forge_write_files import (
    build_manifest_payload,
    build_summary_meta_payload,
    execute_forge_write,
    write_json_atomic,
    write_jsonl_atomic,
    write_text_atomic,
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

    def test_write_text_atomic_writes_and_replaces_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "summary" / "forge.md"

            write_text_atomic(dest, "first\n")
            write_text_atomic(dest, "second\n")

            self.assertEqual(dest.read_text(encoding="utf-8"), "second\n")
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

    def test_execute_forge_write_writes_manifest_and_optional_state_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = {"new_sid": "sid", "written": False}
            replay = {"messages": ["hello"]}

            updated = execute_forge_write(
                project_dir=root / "project",
                manifest_dir=root / "manifest",
                replay_file=root / "state" / "replay.json",
                summary_file=root / "state" / "summary.md",
                summary_meta=root / "state" / "summary-meta.json",
                new_sid="sid",
                forged=[
                    {
                        "type": "user",
                        "message": {"role": "user", "content": [{"type": "text", "text": "hello"}]},
                    }
                ],
                replay=replay,
                summary=summary,
                forge_summary=" summary ",
                summary_info={
                    "write_summary": True,
                    "dropped_events": 2,
                    "dropped_chars": 40,
                    "dropped_hash": "drop",
                    "previous_hash": "prev",
                    "status": "updated",
                    "provider": "provider",
                    "prompt_file": "prompt.md",
                },
                source=root / "source.jsonl",
                summary_updated_at="2026-07-02T01:00:00Z",
                manifest_created_at="2026-07-02T01:00:01Z",
                summary_hash="hash",
            )

            self.assertTrue((root / "project" / "sid.jsonl").exists())
            self.assertEqual((root / "state" / "summary.md").read_text(encoding="utf-8"), "summary\n")
            self.assertEqual((root / "manifest" / "sid.summary.md").read_text(encoding="utf-8"), "summary\n")
            replay_payload = json.loads((root / "state" / "replay.json").read_text(encoding="utf-8"))
            self.assertEqual(replay_payload["new_sid"], "sid")
            meta = json.loads((root / "state" / "summary-meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["summary_hash"], "hash")
            self.assertEqual(meta["provider"], "provider")
            manifest = json.loads((root / "manifest" / "sid.manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["written"])
            self.assertEqual(manifest["created_at"], "2026-07-02T01:00:01Z")
            self.assertTrue(manifest["summary_snapshot"].endswith("sid.summary.md"))
            self.assertFalse(summary["written"])
            self.assertNotIn("new_sid", replay)
            self.assertTrue(updated["written"])
            self.assertTrue(updated["replay_file"].endswith("replay.json"))

    def test_execute_forge_write_can_skip_replay_and_summary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            updated = execute_forge_write(
                project_dir=root / "project",
                manifest_dir=root / "manifest",
                replay_file=root / "state" / "replay.json",
                summary_file=root / "state" / "summary.md",
                summary_meta=root / "state" / "summary-meta.json",
                new_sid="sid",
                forged=[],
                replay=None,
                summary={"new_sid": "sid", "written": False},
                forge_summary="",
                summary_info={"write_summary": False},
                source="source.jsonl",
                summary_updated_at="updated",
                manifest_created_at="created",
                summary_hash="hash",
            )

            self.assertTrue((root / "project" / "sid.jsonl").exists())
            self.assertTrue((root / "manifest" / "sid.manifest.json").exists())
            self.assertFalse((root / "state").exists())
            self.assertNotIn("summary_snapshot", updated)
            self.assertNotIn("replay_file", updated)


if __name__ == "__main__":
    unittest.main()
