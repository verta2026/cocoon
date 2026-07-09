import json
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from bridge.history import (
    list_conversation_days,
    list_conversation_sessions,
    normalize_history_row,
    read_conversation_day,
    read_conversation_messages,
    search_conversations,
)


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


class NormalizeHistoryRowTest(unittest.TestCase):
    def test_group_sender_prefix_becomes_channel_role(self):
        row = normalize_history_row(
            {"role": "user", "content": "[alice] hello there"}, "group"
        )
        self.assertEqual(row["role"], "channel")
        self.assertEqual(row["sender"], "alice")
        self.assertEqual(row["content"], "hello there")

    def test_unprefixed_group_row_stays_main_user(self):
        row = normalize_history_row({"role": "user", "content": "my own words"}, "group")
        self.assertEqual(row["role"], "user")
        self.assertNotIn("sender", row)

    def test_placeholder_prefix_is_not_a_sender(self):
        row = normalize_history_row(
            {"role": "user", "content": "[image]"},
            "group",
            sender_placeholders=frozenset({"image"}),
        )
        self.assertEqual(row["role"], "user")

    def test_colon_prefix_is_not_a_sender(self):
        row = normalize_history_row(
            {"role": "user", "content": "[sticker:cat.jpg]"}, "group"
        )
        self.assertEqual(row["role"], "user")

    def test_channel_tag_from_other_group_member(self):
        content = (
            '<channel source="plugin" chat_id="-100777" message_id="1"'
            ' user="alice" user_id="42" ts="2026-07-01T00:00:00Z">\nhi &amp; bye\n</channel>'
        )
        row = normalize_history_row(
            {"role": "user", "content": content}, "main", main_user_id="7"
        )
        self.assertEqual(row["role"], "channel")
        self.assertEqual(row["sender"], "alice")
        self.assertEqual(row["content"], "hi & bye")
        self.assertEqual(row["channel"], "group")

    def test_channel_tag_from_main_user_stays_user(self):
        content = (
            '<channel source="plugin" chat_id="-100777" message_id="2"'
            ' user="owner" user_id="7" ts="2026-07-01T00:00:00Z">mine</channel>'
        )
        row = normalize_history_row(
            {"role": "user", "content": content}, "main", main_user_id="7"
        )
        self.assertEqual(row["role"], "user")
        self.assertEqual(row["content"], "mine")

    def test_dm_channel_tag_stays_user(self):
        content = (
            '<channel source="plugin" chat_id="7" message_id="3"'
            ' user="owner" user_id="7" ts="2026-07-01T00:00:00Z">dm text</channel>'
        )
        row = normalize_history_row(
            {"role": "user", "content": content}, "main", main_user_id="7"
        )
        self.assertEqual(row["role"], "user")
        self.assertEqual(row["channel"], "dm")

    def test_assistant_rows_untouched(self):
        row = normalize_history_row(
            {"role": "assistant", "content": "[alice] not a sender"}, "group"
        )
        self.assertEqual(row["role"], "assistant")


class ConversationDaysTest(unittest.TestCase):
    def test_lists_days_across_subdirs_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_jsonl(root / "2026-06-29_1200_session.jsonl", [{"role": "user", "content": "a"}])
            write_jsonl(root / "2026-06-30_0900_session.jsonl", [{"role": "user", "content": "b"}])
            write_jsonl(
                root / "group" / "2026-06-30_0900_group.jsonl",
                [{"role": "user", "content": "c"}, {"role": "assistant", "content": "d"}],
            )

            days = list_conversation_days(root)

            self.assertEqual([d["date"] for d in days], ["2026-06-30", "2026-06-29"])
            self.assertEqual(days[0]["sessions"], 2)
            self.assertEqual(days[0]["messages"], 3)

    def test_read_day_merges_dedups_sorts_and_normalizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_jsonl(
                root / "2026-06-30_0900_session.jsonl",
                [
                    {"role": "assistant", "content": "later", "timestamp": "2026-06-30T02:00:00Z"},
                    {"role": "assistant", "content": "later", "timestamp": "2026-06-30T02:00:00Z"},
                ],
            )
            write_jsonl(
                root / "group" / "2026-06-30_0900_group.jsonl",
                [{"role": "user", "content": "[alice] early", "timestamp": "2026-06-30T01:00:00Z"}],
            )
            write_jsonl(root / "2026-06-29_1200_session.jsonl", [{"role": "user", "content": "other day"}])

            msgs = read_conversation_day(root, "2026-06-30")

            self.assertEqual([m["content"] for m in msgs], ["early", "later"])
            self.assertEqual(msgs[0]["role"], "channel")
            self.assertEqual(msgs[0]["sender"], "alice")
            self.assertEqual(msgs[0]["kind"], "group")

    def test_read_day_rejects_bad_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(HTTPException):
                read_conversation_day(Path(tmp), "../etc")


class SearchConversationsTest(unittest.TestCase):
    def test_search_matches_normalized_content_with_snippet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_jsonl(
                root / "group" / "2026-06-30_0900_group.jsonl",
                [{"role": "user", "content": "[alice] the needle is here", "timestamp": "2026-06-30T01:00:00Z"}],
            )

            results = search_conversations(root, "NEEDLE")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["role"], "channel")
            self.assertEqual(results[0]["sender"], "alice")
            self.assertEqual(results[0]["date"], "2026-06-30")
            self.assertIn("needle", results[0]["snippet"])
            self.assertNotIn("[alice]", results[0]["snippet"])

    def test_search_respects_limit_and_empty_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_jsonl(
                root / "2026-06-30_0900_session.jsonl",
                [{"role": "user", "content": f"needle {i}"} for i in range(5)],
            )

            self.assertEqual(len(search_conversations(root, "needle", limit=2)), 2)
            self.assertEqual(search_conversations(root, "   "), [])
