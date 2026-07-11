import unittest

from bridge.chat_history import chat_history_months, chat_history_page, chat_history_search


def _msg(epoch_ms, content, role="assistant"):
    return {"id": f"{epoch_ms:015d}-abcd1234", "role": role, "content": content, "ts": "", "sender": ""}


MSGS = [
    _msg(1720000000000, "good morning"),
    _msg(1720000060000, "the lemon tree grew", role="user"),
    _msg(1720086400000, "second day starts"),
]


class ChatHistoryTest(unittest.TestCase):
    def test_months_index_counts_days_and_anchors(self):
        payload = chat_history_months(MSGS)
        months = payload["months"]
        self.assertEqual(sum(m["count"] for m in months), 3)
        days = [d for m in months for d in m["days"]]
        self.assertEqual(len(days), 2)
        # 每天的锚点是当天第一条的 id，预览取首条非空文字
        first_day = min(days, key=lambda d: d["date"])
        self.assertEqual(first_day["first_id"], MSGS[0]["id"])
        self.assertEqual(first_day["preview"], "good morning")

    def test_search_returns_snippets_newest_first(self):
        payload = chat_history_search(MSGS, "day")
        self.assertEqual(len(payload["results"]), 1)
        hit = payload["results"][0]
        self.assertEqual(hit["id"], MSGS[2]["id"])
        self.assertIn("second day", hit["snippet"])
        self.assertEqual(chat_history_search(MSGS, ""), {"results": []})

    def test_page_three_cursors(self):
        tail = chat_history_page(MSGS, limit=2)
        self.assertEqual([m["id"] for m in tail["messages"]], [MSGS[1]["id"], MSGS[2]["id"]])
        self.assertTrue(tail["has_more"])

        older = chat_history_page(MSGS, before=MSGS[1]["id"], limit=2)
        self.assertEqual([m["id"] for m in older["messages"]], [MSGS[0]["id"]])
        self.assertFalse(older["has_more"])

        newer = chat_history_page(MSGS, after=MSGS[0]["id"], limit=1)
        self.assertEqual([m["id"] for m in newer["messages"]], [MSGS[1]["id"]])
        self.assertTrue(newer["has_more_after"])

        window = chat_history_page(MSGS, around=MSGS[1]["id"], limit=3)
        self.assertEqual(window["target"], MSGS[1]["id"])
        self.assertEqual(len(window["messages"]), 3)
