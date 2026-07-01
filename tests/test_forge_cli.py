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


if __name__ == "__main__":
    unittest.main()
