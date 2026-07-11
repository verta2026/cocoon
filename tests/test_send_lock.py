import asyncio
import unittest

import server


class SendLockTest(unittest.IsolatedAsyncioTestCase):
    async def test_send_waits_for_global_lock(self):
        calls = []
        originals = {
            "verify_token": server.verify_token,
            "tmux_exists": server.tmux_exists,
            "claude_running": server.claude_running,
            "dismiss_resume_summary_prompt": server.dismiss_resume_summary_prompt,
            "tmux_send": server.tmux_send,
            "wait_for_claude_tui": server.wait_for_claude_tui,
        }
        try:
            server.verify_token = lambda request: None
            server.tmux_exists = lambda: True
            server.claude_running = lambda: True
            server.dismiss_resume_summary_prompt = lambda: False
            server.tmux_send = lambda text: calls.append(text)
            server.wait_for_claude_tui = lambda timeout=20: True

            await server.SEND_LOCK.acquire()
            task = asyncio.create_task(server.send_message(server.Message(text="hello"), object()))
            await asyncio.sleep(0)

            self.assertFalse(task.done())
            self.assertEqual(calls, [])

            server.SEND_LOCK.release()
            result = await task

            self.assertEqual(result, {"sent": True, "length": 5})
            self.assertEqual(calls, ["hello"])
        finally:
            if server.SEND_LOCK.locked():
                server.SEND_LOCK.release()
            server.verify_token = originals["verify_token"]
            server.tmux_exists = originals["tmux_exists"]
            server.claude_running = originals["claude_running"]
            server.dismiss_resume_summary_prompt = originals["dismiss_resume_summary_prompt"]
            server.tmux_send = originals["tmux_send"]
            server.wait_for_claude_tui = originals["wait_for_claude_tui"]

    async def test_send_reports_failure_when_tui_not_drawn(self):
        calls = []
        originals = {
            "verify_token": server.verify_token,
            "tmux_exists": server.tmux_exists,
            "claude_running": server.claude_running,
            "dismiss_resume_summary_prompt": server.dismiss_resume_summary_prompt,
            "tmux_send": server.tmux_send,
            "wait_for_claude_tui": server.wait_for_claude_tui,
        }
        try:
            server.verify_token = lambda request: None
            server.tmux_exists = lambda: True
            server.claude_running = lambda: True
            server.dismiss_resume_summary_prompt = lambda: False
            server.tmux_send = lambda text: calls.append(text)
            server.wait_for_claude_tui = lambda timeout=20: False

            result = await server.send_message(server.Message(text="hello"), object())

            self.assertEqual(result, {"sent": False, "length": 5})
            self.assertEqual(calls, [])
        finally:
            if server.SEND_LOCK.locked():
                server.SEND_LOCK.release()
            server.verify_token = originals["verify_token"]
            server.tmux_exists = originals["tmux_exists"]
            server.claude_running = originals["claude_running"]
            server.dismiss_resume_summary_prompt = originals["dismiss_resume_summary_prompt"]
            server.tmux_send = originals["tmux_send"]
            server.wait_for_claude_tui = originals["wait_for_claude_tui"]


if __name__ == "__main__":
    unittest.main()
