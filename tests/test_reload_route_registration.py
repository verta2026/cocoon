import unittest

from bridge.reload_routes import AutoReloadRequest, register_reload_routes


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorate(func):
            self.routes[("GET", path)] = func
            return func
        return decorate

    def post(self, path):
        def decorate(func):
            self.routes[("POST", path)] = func
            return func
        return decorate

    def delete(self, path):
        def decorate(func):
            self.routes[("DELETE", path)] = func
            return func
        return decorate


class ReloadRouteRegistrationTest(unittest.TestCase):
    def test_registers_reload_and_session_control_routes(self):
        app = FakeApp()
        handlers = {
            "get_forge_auto_reload": object(),
            "set_forge_auto_reload": object(),
            "reload_status": object(),
            "set_reload_force": object(),
            "clear_reload_force": object(),
            "new_session": object(),
            "continue_session": object(),
            "reload_session": object(),
            "forge_reload_session": object(),
        }

        register_reload_routes(app, **handlers)

        self.assertIs(app.routes[("GET", "/forge-auto-reload")], handlers["get_forge_auto_reload"])
        self.assertIs(app.routes[("POST", "/forge-auto-reload")], handlers["set_forge_auto_reload"])
        self.assertIs(app.routes[("GET", "/reload-status")], handlers["reload_status"])
        self.assertIs(app.routes[("POST", "/reload-force")], handlers["set_reload_force"])
        self.assertIs(app.routes[("DELETE", "/reload-force")], handlers["clear_reload_force"])
        self.assertIs(app.routes[("POST", "/new-session")], handlers["new_session"])
        self.assertIs(app.routes[("POST", "/continue-session")], handlers["continue_session"])
        self.assertIs(app.routes[("POST", "/reload-session")], handlers["reload_session"])
        self.assertIs(app.routes[("POST", "/forge-reload-session")], handlers["forge_reload_session"])

    def test_auto_reload_request_model(self):
        self.assertTrue(AutoReloadRequest(paused=True).paused)
        self.assertFalse(AutoReloadRequest(paused=False).paused)


if __name__ == "__main__":
    unittest.main()
