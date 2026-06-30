import unittest

from fastapi import HTTPException

import server


class OutputHelpersTest(unittest.TestCase):
    def test_captured_output_returns_terminal_text(self):
        original_exists = server.tmux_exists
        original_capture = server.tmux_capture
        try:
            server.tmux_exists = lambda: True
            server.tmux_capture = lambda lines=200: f"captured {lines}"

            self.assertEqual(server.captured_output_or_404(123), "captured 123")
        finally:
            server.tmux_exists = original_exists
            server.tmux_capture = original_capture

    def test_captured_output_raises_when_session_missing(self):
        original_exists = server.tmux_exists
        try:
            server.tmux_exists = lambda: False

            with self.assertRaises(HTTPException) as ctx:
                server.captured_output_or_404()

            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            server.tmux_exists = original_exists


if __name__ == "__main__":
    unittest.main()
