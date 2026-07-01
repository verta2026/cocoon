import asyncio
import unittest
from types import SimpleNamespace

from bridge.push_routes import register_push_routes


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._decorator("GET", path)

    def post(self, path):
        return self._decorator("POST", path)

    def _decorator(self, method, path):
        def decorate(func):
            self.routes[(method, path)] = func
            return func
        return decorate


class PushRoutesTest(unittest.TestCase):
    def test_registers_push_routes(self):
        app = FakeApp()
        calls = []

        def verify_token(request):
            calls.append(("verify", request.name))

        def push_public_key():
            calls.append(("key",))
            return {"publicKey": "test-key"}

        def push_status():
            calls.append(("status",))
            return {"enabled": True, "subscriptions": 1}

        def push_subscribe(subscription):
            calls.append(("subscribe", subscription))
            return {"ok": True}

        register_push_routes(
            app,
            verify_token=verify_token,
            push_public_key=push_public_key,
            push_status=push_status,
            push_subscribe=push_subscribe,
        )

        key = asyncio.run(app.routes[("GET", "/push/key")](SimpleNamespace(name="key")))
        status = asyncio.run(app.routes[("GET", "/push/status")](SimpleNamespace(name="status")))
        subscribed = asyncio.run(
            app.routes[("POST", "/push/subscribe")](
                {"endpoint": "https://example.invalid/push"},
                SimpleNamespace(name="subscribe"),
            )
        )

        self.assertEqual(key, {"publicKey": "test-key"})
        self.assertEqual(status, {"enabled": True, "subscriptions": 1})
        self.assertEqual(subscribed, {"ok": True})
        self.assertEqual(calls, [
            ("verify", "key"),
            ("key",),
            ("verify", "status"),
            ("status",),
            ("verify", "subscribe"),
            ("subscribe", {"endpoint": "https://example.invalid/push"}),
        ])


if __name__ == "__main__":
    unittest.main()
