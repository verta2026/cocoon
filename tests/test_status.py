import tempfile
import unittest
from pathlib import Path

import server


class StatusRouteTest(unittest.IsolatedAsyncioTestCase):
    async def test_status_reports_auto_reload_pause_state(self):
        originals = {
            "verify_token": server.verify_token,
            "tmux_exists": server.tmux_exists,
            "pane_command": server.pane_command,
            "claude_running": server.claude_running,
            "claude_busy": server.claude_busy,
            "dismiss_resume_summary_prompt": server.dismiss_resume_summary_prompt,
            "dismiss_trust_prompt": server.dismiss_trust_prompt,
            "pause_file": server.AUTO_RELOAD_PAUSE_FILE,
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                pause_file = Path(tmp) / ".paused"
                pause_file.write_text("manual-pause\n", encoding="utf-8")

                server.verify_token = lambda request: None
                server.tmux_exists = lambda: True
                server.pane_command = lambda: "claude"
                server.claude_running = lambda: True
                server.claude_busy = lambda: False
                server.dismiss_resume_summary_prompt = lambda: False
                server.dismiss_trust_prompt = lambda: False
                server.AUTO_RELOAD_PAUSE_FILE = pause_file

                result = await server.status(object())

                self.assertTrue(result["auto_reload_paused"])
                self.assertTrue(result["alive"])
                self.assertTrue(result["running"])
        finally:
            server.verify_token = originals["verify_token"]
            server.tmux_exists = originals["tmux_exists"]
            server.pane_command = originals["pane_command"]
            server.claude_running = originals["claude_running"]
            server.claude_busy = originals["claude_busy"]
            server.dismiss_resume_summary_prompt = originals["dismiss_resume_summary_prompt"]
            server.dismiss_trust_prompt = originals["dismiss_trust_prompt"]
            server.AUTO_RELOAD_PAUSE_FILE = originals["pause_file"]


if __name__ == "__main__":
    unittest.main()
