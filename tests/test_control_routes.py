import unittest

from bridge.control_routes import register_control_routes


class FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        def decorate(func):
            self.routes[("POST", path)] = func
            return func
        return decorate


class ControlRouteRegistrationTest(unittest.TestCase):
    def test_registers_escape_route(self):
        app = FakeApp()
        send_escape = object()

        register_control_routes(app, send_escape=send_escape)

        self.assertIs(app.routes[("POST", "/escape")], send_escape)


if __name__ == "__main__":
    unittest.main()
