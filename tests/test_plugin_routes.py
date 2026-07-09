import asyncio
import unittest
from types import SimpleNamespace

from bridge.plugin_routes import register_json_plugin_routes


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path, **kwargs):
        def decorate(func):
            self.routes[("GET", path)] = (func, kwargs)
            return func
        return decorate

    def post(self, path, **kwargs):
        def decorate(func):
            self.routes[("POST", path)] = (func, kwargs)
            return func
        return decorate


class FakeRequest:
    def __init__(self, payload=None, name="request"):
        self.payload = payload or {}
        self.name = name

    async def json(self):
        return self.payload


class PluginRouteRegistrationTest(unittest.TestCase):
    def test_registers_generic_plugin_api_state_and_ui_routes(self):
        app = FakeApp()
        calls = []

        def verify_token(request):
            calls.append(("verify", request.name))

        def api_request(path, method, payload=None):
            calls.append(("api", path, method, payload))
            return {"path": path, "method": method, "payload": payload}

        register_json_plugin_routes(
            app,
            prefix="example",
            verify_token=verify_token,
            state_payload=lambda: {"ok": True},
            api_request=api_request,
            ui_html="<main>Example</main>",
        )

        state = asyncio.run(app.routes[("GET", "/example/state")][0](FakeRequest(name="state")))
        get_payload = asyncio.run(app.routes[("GET", "/example/api/{path:path}")][0]("status", FakeRequest(name="get")))
        post_payload = asyncio.run(
            app.routes[("POST", "/example/api/{path:path}")][0](
                "command",
                FakeRequest({"text": "go"}, name="post"),
            )
        )
        ui_response = asyncio.run(app.routes[("GET", "/example")][0]())

        self.assertEqual(state, {"ok": True})
        self.assertEqual(get_payload, {"path": "status", "method": "GET", "payload": None})
        self.assertEqual(post_payload, {"path": "command", "method": "POST", "payload": {"text": "go"}})
        self.assertIn(b"Example", ui_response.body)
        self.assertEqual(
            calls,
            [
                ("verify", "state"),
                ("verify", "get"),
                ("api", "status", "GET", None),
                ("verify", "post"),
                ("api", "command", "POST", {"text": "go"}),
            ],
        )

    def test_can_register_plugin_without_state_or_ui(self):
        app = FakeApp()

        register_json_plugin_routes(
            app,
            prefix="/example/",
            verify_token=lambda request: None,
            api_request=lambda path, method, payload=None: {},
        )

        self.assertIn(("GET", "/example/api/{path:path}"), app.routes)
        self.assertIn(("POST", "/example/api/{path:path}"), app.routes)
        self.assertNotIn(("GET", "/example/state"), app.routes)
        self.assertNotIn(("GET", "/example"), app.routes)

    def test_rejects_empty_plugin_prefix(self):
        with self.assertRaises(ValueError):
            register_json_plugin_routes(
                FakeApp(),
                prefix="",
                verify_token=lambda request: None,
                api_request=lambda path, method, payload=None: {},
            )


if __name__ == "__main__":
    unittest.main()
