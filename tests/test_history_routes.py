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
