import unittest

from bridge.interaction_routes import register_interaction_routes


class FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        def decorate(func):
            self.routes[("POST", path)] = func
            return func
        return decorate


class InteractionRouteRegistrationTest(unittest.TestCase):
    def test_registers_start_and_send_routes(self):
        app = FakeApp()
        start_session = object()
        send_message = object()

        register_interaction_routes(app, start_session=start_session, send_message=send_message)

        self.assertIs(app.routes[("POST", "/start")], start_session)
        self.assertIs(app.routes[("POST", "/send")], send_message)


if __name__ == "__main__":
    unittest.main()
