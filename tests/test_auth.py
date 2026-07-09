import unittest

from server import bearer_token_matches, token_matches


class AuthHelpersTest(unittest.TestCase):
    def test_token_matches_configured_token(self):
        self.assertTrue(token_matches("cocoon-default-token"))
        self.assertFalse(token_matches("wrong-token"))
        self.assertFalse(token_matches(None))

    def test_bearer_token_matches_authorization_header(self):
        self.assertTrue(bearer_token_matches("Bearer cocoon-default-token"))
        self.assertFalse(bearer_token_matches("Bearer wrong-token"))
        self.assertFalse(bearer_token_matches("cocoon-default-token"))


if __name__ == "__main__":
    unittest.main()
