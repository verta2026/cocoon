import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace

from bridge.history_routes import register_history_routes


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorate(func):
            self.routes[("GET", path)] = func
            return func
        return decorate


class HistoryRoutesTest(unittest.TestCase):
    def test_registers_wrapped_history_routes(self):
        app = FakeApp()
        calls = []
        conversations_dir = Path("/tmp/conversations")

        def verify_token(request):
            calls.append(("verify", request.name))

        def list_sessions(conversations_dir):
            calls.append(("list", str(conversations_dir)))
            return [{"file": "session.jsonl"}]

        def read_messages(conversations_dir, file_id):
            calls.append(("read", str(conversations_dir), file_id))
            return [{"role": "user", "content": "hello"}]

        register_history_routes(
            app,
            verify_token=verify_token,
            list_conversation_sessions=list_sessions,
            read_conversation_messages=read_messages,
            conversations_dir=conversations_dir,
            wrap_sessions=True,
            wrap_messages=True,
        )

        sessions = asyncio.run(app.routes[("GET", "/history")](SimpleNamespace(name="list")))
        messages = asyncio.run(
            app.routes[("GET", "/history/{file_id:path}")](
                "session.jsonl",
                SimpleNamespace(name="detail"),
            )
        )

        self.assertEqual(sessions, {"sessions": [{"file": "session.jsonl"}]})
        self.assertEqual(messages, {"file": "session.jsonl", "messages": [{"role": "user", "content": "hello"}]})
        self.assertEqual(calls, [
            ("verify", "list"),
            ("list", str(conversations_dir)),
            ("verify", "detail"),
            ("read", str(conversations_dir), "session.jsonl"),
        ])

    def test_can_return_unwrapped_vps_style_payloads(self):
        app = FakeApp()

        register_history_routes(
            app,
            verify_token=lambda request: None,
            list_conversation_sessions=lambda conversations_dir: [{"file": "session.jsonl"}],
            read_conversation_messages=lambda conversations_dir, file_id: [{"role": "user"}],
            conversations_dir=Path("/tmp/conversations"),
        )

        sessions = asyncio.run(app.routes[("GET", "/history")](SimpleNamespace(name="list")))
        messages = asyncio.run(
            app.routes[("GET", "/history/{file_id:path}")](
                "session.jsonl",
                SimpleNamespace(name="detail"),
            )
        )

        self.assertEqual(sessions, [{"file": "session.jsonl"}])
        self.assertEqual(messages, [{"role": "user"}])


if __name__ == "__main__":
    unittest.main()


class OptionalDayAndSearchRoutesTest(unittest.TestCase):
    def test_day_and_search_routes_absent_by_default(self):
        app = FakeApp()
        register_history_routes(
            app,
            verify_token=lambda request: None,
            list_conversation_sessions=lambda d: [],
            read_conversation_messages=lambda d, f: [],
            conversations_dir=Path("/tmp/conversations"),
        )
        self.assertNotIn(("GET", "/history-days"), app.routes)
        self.assertNotIn(("GET", "/history-day/{date}"), app.routes)
        self.assertNotIn(("GET", "/history-search"), app.routes)

    def test_registers_day_and_search_routes_when_provided(self):
        app = FakeApp()
        calls = []
        conversations_dir = Path("/tmp/conversations")

        register_history_routes(
            app,
            verify_token=lambda request: calls.append("verify"),
            list_conversation_sessions=lambda d: [],
            read_conversation_messages=lambda d, f: [],
            conversations_dir=conversations_dir,
            list_conversation_days=lambda d: [{"date": "2026-06-30"}],
            read_conversation_day=lambda d, date: [{"role": "user", "content": date}],
            search_conversations=lambda d, q, limit: [{"snippet": q, "limit": limit}],
        )

        days = asyncio.run(app.routes[("GET", "/history-days")](SimpleNamespace()))
        day = asyncio.run(app.routes[("GET", "/history-day/{date}")]("2026-06-30", SimpleNamespace()))
        found = asyncio.run(app.routes[("GET", "/history-search")](SimpleNamespace(), q="hi", limit=9000))

        self.assertEqual(days, [{"date": "2026-06-30"}])
        self.assertEqual(day[0]["content"], "2026-06-30")
        self.assertEqual(found[0]["snippet"], "hi")
        self.assertEqual(found[0]["limit"], 500)
        self.assertEqual(calls.count("verify"), 3)
