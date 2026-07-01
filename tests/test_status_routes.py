import unittest

from bridge.status_routes import register_status_route


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorate(func):
            self.routes[("GET", path)] = func
            return func
        return decorate


class StatusRouteRegistrationTest(unittest.TestCase):
    def test_registers_status_route(self):
        app = FakeApp()
        status = object()

        register_status_route(app, status=status)

        self.assertIs(app.routes[("GET", "/status")], status)


if __name__ == "__main__":
    unittest.main()
