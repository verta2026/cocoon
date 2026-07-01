import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from bridge.auth import (
    bearer_token_matches,
    request_token_matches,
    token_matches,
    verify_request_token,
)


class AuthHelpersTest(unittest.TestCase):
    def test_token_matches_expected_token(self):
        self.assertTrue(token_matches("secret", "secret"))
        self.assertFalse(token_matches("wrong", "secret"))
        self.assertFalse(token_matches(None, "secret"))

    def test_bearer_token_matches_authorization_header(self):
        self.assertTrue(bearer_token_matches("Bearer secret", "secret"))
        self.assertFalse(bearer_token_matches("Bearer wrong", "secret"))
        self.assertFalse(bearer_token_matches("secret", "secret"))

    def test_request_token_matches_bearer_cookie_or_query(self):
        self.assertTrue(
            request_token_matches(
                SimpleNamespace(headers={"Authorization": "Bearer secret"}, cookies={}, query_params={}),
                "secret",
            )
        )
        self.assertTrue(
            request_token_matches(
                SimpleNamespace(headers={}, cookies={"token": "secret"}, query_params={}),
                "secret",
            )
        )
        self.assertTrue(
            request_token_matches(
                SimpleNamespace(headers={}, cookies={}, query_params={"token": "secret"}),
                "secret",
            )
        )
        self.assertFalse(
            request_token_matches(
                SimpleNamespace(headers={}, cookies={"token": "wrong"}, query_params={}),
                "secret",
            )
        )

    def test_verify_request_token_rejects_bad_token(self):
        request = SimpleNamespace(headers={}, cookies={}, query_params={})

        with self.assertRaises(HTTPException) as ctx:
            verify_request_token(request, "secret")

        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
