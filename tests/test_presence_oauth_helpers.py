import base64
import hashlib
import unittest
from urllib.parse import parse_qs, urlparse

from presence.oauth_helpers import (
    authorization_url,
    b64url_no_padding,
    basic_auth_header,
    pkce_s256_challenge,
)


class PresenceOauthHelpersTests(unittest.TestCase):
    def test_b64url_no_padding_removes_padding(self):
        self.assertEqual(b64url_no_padding(b"hello"), "aGVsbG8")
        self.assertNotIn("=", b64url_no_padding(b"hi"))

    def test_pkce_s256_challenge_matches_sha256_urlsafe_encoding(self):
        verifier = "verifier"
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()

        self.assertEqual(pkce_s256_challenge(verifier), expected)

    def test_basic_auth_header_requires_both_client_fields(self):
        self.assertIsNone(basic_auth_header("client", None))
        self.assertIsNone(basic_auth_header(None, "secret"))
        self.assertEqual(
            basic_auth_header("client", "secret"),
            "Basic " + base64.b64encode(b"client:secret").decode(),
        )

    def test_authorization_url_encodes_query_params(self):
        url = authorization_url(
            "https://example.test/oauth",
            {
                "client_id": "client",
                "scope": "tweet.read users.read",
                "state": "a/b",
            },
        )
        parsed = urlparse(url)

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "example.test")
        self.assertEqual(parsed.path, "/oauth")
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "client_id": ["client"],
                "scope": ["tweet.read users.read"],
                "state": ["a/b"],
            },
        )


if __name__ == "__main__":
    unittest.main()
