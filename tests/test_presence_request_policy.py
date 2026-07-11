import unittest

from presence.request_policy import TOKEN_ONLY, TOKEN_OR_COOKIE, post_auth_mode


class PresenceRequestPolicyTest(unittest.TestCase):
    def test_browser_write_paths_allow_token_or_cookie(self):
        mode = post_auth_mode(
            "/write",
            browser_write_paths={"/write"},
            token_only_paths={"/device"},
        )

        self.assertEqual(mode, TOKEN_OR_COOKIE)

    def test_token_only_paths_require_token(self):
        mode = post_auth_mode(
            "/device",
            browser_write_paths={"/write"},
            token_only_paths={"/device"},
        )

        self.assertEqual(mode, TOKEN_ONLY)

    def test_unknown_path_uses_default(self):
        self.assertEqual(post_auth_mode("/unknown"), TOKEN_ONLY)
        self.assertEqual(post_auth_mode("/unknown", default=TOKEN_OR_COOKIE), TOKEN_OR_COOKIE)


if __name__ == "__main__":
    unittest.main()
