import json
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from bridge.history import list_conversation_sessions, read_conversation_messages


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class HistoryTest(unittest.TestCase):
    def test_lists_sessions_without_copying_message_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_jsonl(
                root / "2026-06-29_1200_session.jsonl",
                [
                    {"role": "assistant", "content": "hello"},
                    {"role": "user", "content": "first user message"},
                ],
            )
            write_jsonl(
                root / "dm" / "2026-06-28_dm.jsonl",
                [{"role": "user", "content": "dm preview"}],
            )

            sessions = list_conversation_sessions(root)

            self.assertEqual([s["file"] for s in sessions], ["2026-06-29_1200_session.jsonl", "dm/2026-06-28_dm.jsonl"])
            self.assertEqual(sessions[0]["kind"], "main")
            self.assertEqual(sessions[0]["messages"], 2)
            self.assertEqual(sessions[0]["preview"], "first user message")

    def test_read_messages_sorts_by_timestamp_then_file_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_jsonl(
                root / "session.jsonl",
                [
                    {"role": "assistant", "content": "second", "timestamp": "2026-06-29T12:00:02Z"},
                    {"role": "user", "content": "first", "timestamp": "2026-06-29T12:00:01Z"},
                    {"role": "assistant", "content": "no timestamp"},
                ],
            )

            messages = read_conversation_messages(root, "session.jsonl")

            self.assertEqual([m["content"] for m in messages], ["no timestamp", "first", "second"])

    def test_reads_utf8_bom_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "session.jsonl"
            path.write_text('\ufeff{"role":"user","content":"bom ok"}\n', encoding="utf-8")

            sessions = list_conversation_sessions(root)
            messages = read_conversation_messages(root, "session.jsonl")

            self.assertEqual(sessions[0]["preview"], "bom ok")
            self.assertEqual(messages[0]["content"], "bom ok")

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(HTTPException) as ctx:
                read_conversation_messages(root, "../private.jsonl")

            self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
