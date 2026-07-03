import unittest

from bridge.status_routes import build_status_payload, register_status_route


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorate(func):
            self.routes[("GET", path)] = func
            return func
        return decorate


class StatusRouteRegistrationTest(unittest.TestCase):
    def test_build_status_payload_core_fields(self):
        payload = build_status_payload(
            session_name="cocoon",
            alive=True,
            running=True,
            command="claude",
            busy=False,
            auto_reload_paused=False,
            dismissed_resume=True,
            dismissed_trust=False,
        )

        self.assertEqual(
            payload,
            {
                "session": "cocoon",
                "alive": True,
                "running": True,
                "command": "claude",
                "busy": False,
                "auto_reload_paused": False,
                "dismissed_resume": True,
                "dismissed_trust": False,
            },
        )

    def test_build_status_payload_can_include_reload_context(self):
        payload = build_status_payload(
            session_name="cocoon",
            alive=True,
            running=True,
            command="claude",
            busy=False,
            auto_reload_paused=True,
            dismissed_resume=False,
            mode="forge",
            active_mode="forge",
            auto_reload="in-progress",
            context_tokens=42,
            active_threshold=100,
            context_window_1m=False,
            idle_seconds=1800,
            idle_min_context=50,
            check_interval_seconds=30,
            cooldown_seconds=600,
            session_bytes=2048,
            live_archive={"updated": True},
        )

        self.assertEqual(payload["mode"], "forge")
        self.assertEqual(payload["active_mode"], "forge")
        self.assertEqual(payload["auto_reload"], "in-progress")
        self.assertEqual(payload["context_tokens"], 42)
        self.assertEqual(payload["session_bytes"], 2048)
        self.assertEqual(payload["live_archive"], {"updated": True})
        self.assertEqual(
            payload["auto_reload_thresholds"],
            {
                "context_tokens": 100,
                "window_1m": False,
                "idle_seconds": 1800,
                "idle_min_context": 50,
                "check_interval": 30,
                "cooldown": 600,
            },
        )

    def test_registers_status_route(self):
        app = FakeApp()
        status = object()

        register_status_route(app, status=status)

        self.assertIs(app.routes[("GET", "/status")], status)


if __name__ == "__main__":
    unittest.main()
