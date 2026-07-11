import unittest
from unittest.mock import patch

import server


class StartSessionTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_session_uses_configured_tmux_history_limit(self):
        calls = []
        originals = {
            "verify_token": server.verify_token,
            "tmux_exists": server.tmux_exists,
            "tmux_new_session": server.tmux_new_session,
            "start_claude": server.start_claude,
        }
        try:
            server.verify_token = lambda request: None
            server.tmux_exists = lambda: False
            server.tmux_new_session = lambda: calls.append("new-session")
            server.start_claude = lambda: calls.append("start-claude")

            with patch("server.subprocess.run") as run, patch("server.asyncio.sleep", return_value=None):
                result = await server.start_session(object())

            self.assertEqual(result, {"message": "Session started", "session": server.SESSION_NAME})
            run.assert_called_once_with(
                ["tmux", "set-option", "-g", "history-limit", str(server.TMUX_HISTORY_LIMIT)],
                capture_output=True,
            )
            self.assertEqual(calls, ["new-session", "start-claude"])
        finally:
            server.verify_token = originals["verify_token"]
            server.tmux_exists = originals["tmux_exists"]
            server.tmux_new_session = originals["tmux_new_session"]
            server.start_claude = originals["start_claude"]


if __name__ == "__main__":
    unittest.main()
