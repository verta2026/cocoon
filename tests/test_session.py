import unittest
from unittest.mock import patch

from fastapi import HTTPException

import server
from bridge.session import launcher_in_progress, normalized_start_command, start_claude


class SessionHelpersTest(unittest.TestCase):
    def test_default_start_command_is_claude(self):
        self.assertEqual(normalized_start_command(None), "claude")
        self.assertEqual(normalized_start_command(""), "claude")
        self.assertEqual(normalized_start_command("  claude  "), "claude")

    def test_start_claude_clears_then_sends_configured_command(self):
        calls = []

        start_claude(
            "scripts/start_claude.sh --mode forge-reload",
            lambda: calls.append("clear-input"),
            lambda: calls.append("clear-scrollback"),
            lambda text: calls.append(("send", text)),
        )

        self.assertEqual(
            calls,
            [
                "clear-input",
                "clear-scrollback",
                ("send", "scripts/start_claude.sh --mode forge-reload"),
            ],
        )

    def test_empty_launcher_pattern_disables_process_check(self):
        with patch("bridge.session.subprocess.run") as run:
            self.assertFalse(launcher_in_progress(""))
        run.assert_not_called()


class ContinueSessionRouteTest(unittest.IsolatedAsyncioTestCase):
    async def test_continue_session_is_explicitly_disabled(self):
        original_verify = server.verify_token
        try:
            server.verify_token = lambda request: None
            with self.assertRaises(HTTPException) as ctx:
                await server.continue_session(object())

            self.assertEqual(ctx.exception.status_code, 410)
            self.assertIn("disabled", ctx.exception.detail)
        finally:
            server.verify_token = original_verify


if __name__ == "__main__":
    unittest.main()
