import json
import tempfile
import unittest
from pathlib import Path

from bridge.forge import load_jsonl
from bridge.forge_cli import run


def write_jsonl(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


class ForgeCliTest(unittest.TestCase):
    def test_load_jsonl_reports_bad_json_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.jsonl"
            write_jsonl(path, ['{"ok": true}', "{bad"])

            with self.assertRaisesRegex(ValueError, "bad json"):
                load_jsonl(path)

    def test_run_builds_dry_run_summary_from_explicit_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "session.jsonl"
            write_jsonl(
                source,
                [
                    '{"type":"user","message":{"role":"user","content":[{"type":"text","text":"hello"}]}}',
                    '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"reply"}]}}',
                ],
            )

            summary = run(
                [
                    "--source",
                    str(source),
                    "--project-dir",
                    str(root / "project"),
                    "--manifest-dir",
                    str(root / "manifest"),
                    "--new-session-id",
                    "sid-1",
                ]
            )

            self.assertEqual(summary["source"], str(source))
            self.assertEqual(summary["new_sid"], "sid-1")
            self.assertEqual(summary["source_events"], 2)
            self.assertEqual(summary["sanitized_events"], 2)
            self.assertEqual(summary["kept_events"], 2)
            self.assertFalse(summary["written"])
            self.assertEqual(summary["project_dir"], str(root / "project"))
            self.assertEqual(summary["manifest_dir"], str(root / "manifest"))
            self.assertFalse((root / "project").exists())
            self.assertFalse((root / "manifest").exists())

    def test_run_write_uses_explicit_project_and_manifest_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "session.jsonl"
            project_dir = root / "project"
            manifest_dir = root / "manifest"
            write_jsonl(
                source,
                [
                    '{"type":"user","message":{"role":"user","content":[{"type":"text","text":"hello"}]}}',
                    '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"reply"}]}}',
                ],
            )

            summary = run(
                [
                    "--source",
                    str(source),
                    "--project-dir",
                    str(project_dir),
                    "--manifest-dir",
                    str(manifest_dir),
                    "--new-session-id",
                    "sid-2",
                    "--created-at",
                    "2026-07-01T00:00:00Z",
                    "--write",
                ]
            )

            dest = project_dir / "sid-2.jsonl"
            manifest = manifest_dir / "sid-2.manifest.json"
            self.assertTrue(summary["written"])
            self.assertEqual(summary["dest"], str(dest))
            self.assertEqual(summary["manifest"], str(manifest))
            self.assertTrue(dest.exists())
            self.assertTrue(manifest.exists())
            self.assertIn('"sessionId":"sid-2"', dest.read_text(encoding="utf-8"))
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertTrue(manifest_payload["written"])
            self.assertEqual(manifest_payload["dest"], str(dest))
            self.assertEqual(manifest_payload["manifest"], str(manifest))
            self.assertEqual(manifest_payload["created_at"], "2026-07-01T00:00:00Z")
            self.assertFalse((manifest_dir / "sid-2.summary.md").exists())


if __name__ == "__main__":
    unittest.main()
