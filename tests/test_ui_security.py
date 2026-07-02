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

    def test_chat_ui_filters_generic_forge_summary_diagnostics(self):
        self.assertIn("FORGE_RESUME_READY_", CHAT_HTML)
        self.assertIn("FORGE_CONTEXT_SUMMARY:", CHAT_HTML)
        self.assertIn('"retained_events"', CHAT_HTML)
        self.assertIn('"summary_(?:injected|status|file|meta|chars|dropped_events|dropped_chars|snapshot|provider|prompt_file)"', CHAT_HTML)
        self.assertNotIn("BOND_VERIFY_", CHAT_HTML)


if __name__ == "__main__":
    unittest.main()


class JumpToLatestButtonTest(unittest.TestCase):
    def test_chat_has_jump_to_latest_button(self):
        self.assertIn('id="to-bottom"', CHAT_HTML)
        self.assertIn("updateToBottomBtn", CHAT_HTML)
        self.assertIn("#to-bottom.show", CHAT_HTML)
