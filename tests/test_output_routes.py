import unittest

from bridge.output_routes import (
    build_chat_pure_payload,
    build_messages_payload,
    clamp_messages_limit,
    register_output_routes,
)


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorate(func):
            self.routes[("GET", path)] = func
            return func
        return decorate


class OutputRouteRegistrationTest(unittest.TestCase):
    def test_clamp_messages_limit_bounds_values(self):
        self.assertEqual(clamp_messages_limit(1), 20)
        self.assertEqual(clamp_messages_limit(20), 20)
        self.assertEqual(clamp_messages_limit(300), 300)
        self.assertEqual(clamp_messages_limit(5000), 1000)

    def test_clamp_messages_limit_accepts_custom_bounds(self):
        self.assertEqual(clamp_messages_limit(3, minimum=5, maximum=10), 5)
        self.assertEqual(clamp_messages_limit(30, minimum=5, maximum=10), 10)

    def test_build_messages_payload_core_fields(self):
        self.assertEqual(
            build_messages_payload(messages=[{"role": "user"}], running=True, busy=False),
            {
                "messages": [{"role": "user"}],
                "running": True,
                "busy": False,
                "source": "live-archive",
            },
        )

    def test_build_messages_payload_can_include_auto_reload(self):
        self.assertEqual(
            build_messages_payload(messages=[], running=False, busy=False, auto_reload="in-progress"),
            {
                "messages": [],
                "running": False,
                "busy": False,
                "auto_reload": "in-progress",
                "source": "live-archive",
            },
        )

    def test_registers_output_routes_without_messages_by_default(self):
        app = FakeApp()
        get_output = object()
        get_raw_output = object()

        register_output_routes(app, get_output=get_output, get_raw_output=get_raw_output)

        self.assertIs(app.routes[("GET", "/output")], get_output)
        self.assertIs(app.routes[("GET", "/raw-output")], get_raw_output)
        self.assertNotIn(("GET", "/messages"), app.routes)

    def test_can_register_optional_messages_route(self):
        app = FakeApp()
        get_messages = object()

        register_output_routes(
            app,
            get_output=object(),
            get_raw_output=object(),
            get_messages=get_messages,
        )

        self.assertIs(app.routes[("GET", "/messages")], get_messages)

    def test_can_register_optional_chat_pure_route(self):
        app = FakeApp()
        get_chat_pure = object()

        register_output_routes(
            app,
            get_output=object(),
            get_raw_output=object(),
            get_chat_pure=get_chat_pure,
        )

        self.assertIs(app.routes[("GET", "/chat_pure")], get_chat_pure)
        self.assertNotIn(("GET", "/messages"), app.routes)

    def test_build_chat_pure_payload_fields(self):
        self.assertEqual(
            build_chat_pure_payload(messages=[{"id": "1"}], running=True, busy=False),
            {"messages": [{"id": "1"}], "running": True, "busy": False, "ask": None},
        )

    def test_build_chat_pure_payload_carries_ask(self):
        ask = {"id": "toolu_1", "questions": [{"question": "?"}]}
        payload = build_chat_pure_payload(messages=[], running=True, busy=True, ask=ask)
        self.assertIs(payload["ask"], ask)
        # not running -> no ask field at all (nothing can be pending)
        self.assertNotIn("ask", build_chat_pure_payload(messages=[], running=False, busy=False, ask=ask))


if __name__ == "__main__":
    unittest.main()
