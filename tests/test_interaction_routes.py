import unittest

from bridge.interaction_routes import build_send_payload, build_start_session_payload, register_interaction_routes


class FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        def decorate(func):
            self.routes[("POST", path)] = func
            return func
        return decorate


class InteractionRouteRegistrationTest(unittest.TestCase):
    def test_build_start_session_payload_omits_session_when_absent(self):
        self.assertEqual(build_start_session_payload("Session already running"), {"message": "Session already running"})

    def test_build_start_session_payload_includes_session_when_present(self):
        self.assertEqual(
            build_start_session_payload("Session started", "cocoon"),
            {"message": "Session started", "session": "cocoon"},
        )

    def test_build_send_payload_core_fields(self):
        self.assertEqual(build_send_payload(sent=True, length=5), {"sent": True, "length": 5})

    def test_build_send_payload_optional_reload_fields(self):
        self.assertEqual(
            build_send_payload(sent=False, reloaded=False, reason="launcher-in-progress", length=3),
            {"sent": False, "reloaded": False, "reason": "launcher-in-progress", "length": 3},
        )

    def test_registers_start_and_send_routes(self):
        app = FakeApp()
        start_session = object()
        send_message = object()

        register_interaction_routes(app, start_session=start_session, send_message=send_message)

        self.assertIs(app.routes[("POST", "/start")], start_session)
        self.assertIs(app.routes[("POST", "/send")], send_message)


if __name__ == "__main__":
    unittest.main()
