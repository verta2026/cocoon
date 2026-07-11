import unittest

from bridge.ui import TERMINAL_HTML


class UiSecurityTest(unittest.TestCase):
    # 旧内嵌聊天页已退役（聊天 UI 只有 /app/ 的 React 构建），这里只剩终端页要守。

    def test_terminal_does_not_put_token_in_urls(self):
        self.assertNotIn("?token=", TERMINAL_HTML)
        self.assertNotIn("encodeURIComponent(TOKEN)", TERMINAL_HTML)

    def test_terminal_reads_token_from_storage_not_query(self):
        self.assertIn("localStorage.getItem('cocoon_token')", TERMINAL_HTML)
        self.assertNotIn("URLSearchParams", TERMINAL_HTML)

    def test_terminal_has_no_private_leftovers(self):
        self.assertNotIn("galgame", TERMINAL_HTML.lower())
        self.assertNotIn("mailbox", TERMINAL_HTML.lower())
        self.assertNotIn("PRIVATE_DEPLOYMENT_MARKER_", TERMINAL_HTML)


if __name__ == "__main__":
    unittest.main()
