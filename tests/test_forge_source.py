import json
import tempfile
import unittest
from pathlib import Path

from bridge.forge_source import build_source_window, select_forge_source


ASSISTANT_BLOCKS = {"thinking", "redacted_thinking", "text"}
USER_BLOCKS = {"text"}


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def user(text, timestamp="2026-07-02T00:00:00Z"):
    return {
        "type": "user",
        "timestamp": timestamp,
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def assistant(text, timestamp="2026-07-02T00:01:00Z"):
    return {
        "type": "assistant",
        "timestamp": timestamp,
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


class ForgeSourceTest(unittest.TestCase):
    def test_build_source_window_loads_rows_and_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "session.jsonl"
            write_jsonl(source, [user("hello"), assistant("reply")])

            rows, window = build_source_window(source, 1000, 1000, ASSISTANT_BLOCKS, USER_BLOCKS)

            self.assertEqual(len(rows), 2)
            self.assertEqual(window["clean_events"], 2)
            self.assertEqual(len(window["kept"]), 2)

    def test_select_forge_source_uses_explicit_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "explicit.jsonl"
            write_jsonl(source, [user("hello"), assistant("reply")])

            selected, rows, window, skipped = select_forge_source(
                source=source,
                project_dir=tmp,
                retain_tokens=1000,
                dialogue_tokens=1000,
                assistant_blocks=ASSISTANT_BLOCKS,
                user_blocks=USER_BLOCKS,
            )

            self.assertEqual(selected, source)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(window["kept"]), 2)
            self.assertEqual(skipped, [])

    def test_select_forge_source_skips_newer_unusable_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "bad.jsonl"
            good = root / "good.jsonl"
            write_jsonl(bad, [user("only user", "2026-07-02T02:00:00Z")])
            write_jsonl(good, [user("hello", "2026-07-02T01:00:00Z"), assistant("reply", "2026-07-02T01:01:00Z")])

            selected, rows, window, skipped = select_forge_source(
                source=None,
                project_dir=root,
                retain_tokens=1000,
                dialogue_tokens=1000,
                assistant_blocks=ASSISTANT_BLOCKS,
                user_blocks=USER_BLOCKS,
            )

            self.assertEqual(selected, good)
            self.assertEqual(len(rows), 2)
            self.assertEqual(window["clean_events"], 2)
            self.assertEqual(len(skipped), 1)
            self.assertTrue(skipped[0]["path"].endswith("bad.jsonl"))
            self.assertEqual(skipped[0]["reason"], "no user + text-bearing assistant pair in kept window")

    def test_select_forge_source_raises_when_no_viable_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "no forgeable session"):
                select_forge_source(
                    source=None,
                    project_dir=tmp,
                    retain_tokens=1000,
                    dialogue_tokens=1000,
                    assistant_blocks=ASSISTANT_BLOCKS,
                    user_blocks=USER_BLOCKS,
                )


if __name__ == "__main__":
    unittest.main()
