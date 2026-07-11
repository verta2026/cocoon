import hashlib
import unittest

from presence.auth_helpers import (
    auth_cookie_header,
    cookie_matches,
    parse_login_body,
    password_matches_sha256_prefix,
)


class PresenceAuthHelpersTest(unittest.TestCase):
    def test_cookie_matches_named_cookie(self):
        self.assertTrue(cookie_matches("other=x; session=secret", cookie_name="session", expected_value="secret"))
        self.assertFalse(cookie_matches("session=wrong", cookie_name="session", expected_value="secret"))
        self.assertFalse(cookie_matches("session=secret", cookie_name="session", expected_value=""))

    def test_password_matches_sha256_prefix(self):
        digest = hashlib.sha256(b"password").hexdigest()

        self.assertTrue(password_matches_sha256_prefix("password", digest[:12]))
        self.assertFalse(password_matches_sha256_prefix("password", "bad"))
        self.assertFalse(password_matches_sha256_prefix("password", ""))

    def test_auth_cookie_header_uses_options(self):
        header = auth_cookie_header(
            cookie_name="session",
            cookie_value="secret",
            max_age_seconds=60,
            same_site="Strict",
            secure=False,
            http_only=True,
            path="/app",
        )

        self.assertEqual(header, "session=secret; Path=/app; Max-Age=60; SameSite=Strict; HttpOnly")

    def test_parse_login_body_supports_json_form_and_query(self):
        self.assertEqual(
            parse_login_body(b'{"password":"json"}', "application/json", {"next": "/"}),
            {"password": "json", "next": "/"},
        )
        self.assertEqual(
            parse_login_body(b"password=form", "application/x-www-form-urlencoded", {"next": "/"}),
            {"password": "form", "next": "/"},
        )
        self.assertEqual(
            parse_login_body(b"{bad", "application/json", {"password": "query"}),
            {"password": "query"},
        )


if __name__ == "__main__":
    unittest.main()
