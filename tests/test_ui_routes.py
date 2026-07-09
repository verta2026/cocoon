import unittest

from bridge.ui_routes import register_core_ui_routes


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path, **kwargs):
        def decorate(func):
            self.routes[("GET", path)] = (func, kwargs)
            return func
        return decorate


class UiRouteRegistrationTest(unittest.TestCase):
    def test_registers_chat_and_terminal_routes(self):
        app = FakeApp()
        chat_ui = object()
        terminal_page = object()

        register_core_ui_routes(app, chat_ui=chat_ui, terminal_page=terminal_page)

        self.assertIs(app.routes[("GET", "/chat")][0], chat_ui)
        self.assertIs(app.routes[("GET", "/terminal")][0], terminal_page)
        self.assertNotIn(("GET", "/chat-history"), app.routes)

    def test_can_register_optional_history_route(self):
        app = FakeApp()
        history_ui = object()

        register_core_ui_routes(app, chat_ui=object(), terminal_page=object(), history_ui=history_ui)

        self.assertIs(app.routes[("GET", "/chat-history")][0], history_ui)
        self.assertIn("response_class", app.routes[("GET", "/chat-history")][1])


if __name__ == "__main__":
    unittest.main()
