import unittest

from bridge.output_routes import build_messages_payload, register_output_routes


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorate(func):
            self.routes[("GET", path)] = func
            return func
        return decorate


class OutputRouteRegistrationTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
