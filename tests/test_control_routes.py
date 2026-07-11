import unittest

from bridge.control_routes import (
    TERMINAL_KEYS,
    register_control_routes,
    resolve_terminal_key,
)


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
        self.assertNotIn(("POST", "/key"), app.routes)

    def test_registers_key_route_when_given(self):
        app = FakeApp()
        send_escape, send_key = object(), object()

        register_control_routes(app, send_escape=send_escape, send_key=send_key)

        self.assertIs(app.routes[("POST", "/key")], send_key)


class ResolveTerminalKeyTest(unittest.TestCase):
    def test_allowlisted_keys_resolve_to_tmux_names(self):
        self.assertEqual(resolve_terminal_key("up"), "Up")
        self.assertEqual(resolve_terminal_key("down"), "Down")
        self.assertEqual(resolve_terminal_key("enter"), "Enter")
        self.assertEqual(resolve_terminal_key("esc"), "Escape")

    def test_normalizes_case_and_whitespace(self):
        self.assertEqual(resolve_terminal_key(" Enter "), "Enter")
        self.assertEqual(resolve_terminal_key("ESC"), "Escape")

    def test_rejects_everything_else(self):
        # send-keys 的键位名槽绝不能吃任意字符串
        for bad in ("C-c", "run-shell ls", "Escape; ls", "", None, 3, ["up"]):
            self.assertIsNone(resolve_terminal_key(bad))

    def test_allowlist_is_exactly_four_keys(self):
        self.assertEqual(set(TERMINAL_KEYS), {"up", "down", "enter", "esc"})


if __name__ == "__main__":
    unittest.main()
