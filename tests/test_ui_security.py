import unittest

from bridge.ui import CHAT_HTML


class UiSecurityTest(unittest.TestCase):
    def test_chat_ui_does_not_put_token_in_media_urls(self):
        self.assertNotIn("?token=", CHAT_HTML)
        self.assertNotIn("encodeURIComponent(TOKEN);", CHAT_HTML)

    def test_chat_ui_sets_same_origin_cookie_for_media_requests(self):
        self.assertIn("document.cookie", CHAT_HTML)
        self.assertIn("SameSite=Strict", CHAT_HTML)

    def test_chat_ui_exposes_generic_reload_controls(self):
        self.assertIn("reload session", CHAT_HTML)
        self.assertIn("/reload-session", CHAT_HTML)
        self.assertIn("/forge-auto-reload", CHAT_HTML)
        self.assertNotIn("galgame", CHAT_HTML.lower())
        self.assertNotIn("mailbox", CHAT_HTML.lower())


if __name__ == "__main__":
    unittest.main()
