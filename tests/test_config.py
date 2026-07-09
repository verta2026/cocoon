import importlib
import os
import unittest
from unittest.mock import patch

import config


class ConfigParsingTest(unittest.TestCase):
    def reload_with_env(self, values):
        env = os.environ.copy()
        env.update(values)
        with patch.dict(os.environ, env, clear=True):
            return importlib.reload(config)

    def tearDown(self):
        importlib.reload(config)

    def test_numeric_env_values_are_parsed(self):
        cfg = self.reload_with_env(
            {
                "COCOON_PORT": "9000",
                "COCOON_TMUX_HISTORY_LIMIT": "30000",
                "COCOON_MAX_UPLOAD_MB": "1.5",
                "COCOON_AUTO_RELOAD_CONTEXT_THRESHOLD": "100",
                "COCOON_AUTO_RELOAD_CONTEXT_THRESHOLD_1M": "500",
                "COCOON_AUTO_RELOAD_IDLE_MIN_CONTEXT": "50",
                "COCOON_AUTO_RELOAD_IDLE_SECONDS": "60",
                "COCOON_AUTO_RELOAD_COOLDOWN_SECONDS": "0",
                "COCOON_AUTO_RELOAD_CHECK_INTERVAL_SECONDS": "5",
            }
        )

        self.assertEqual(cfg.PORT, 9000)
        self.assertEqual(cfg.TMUX_HISTORY_LIMIT, 30000)
        self.assertEqual(cfg.MAX_UPLOAD_BYTES, int(1.5 * 1024 * 1024))
        self.assertEqual(cfg.AUTO_RELOAD_CONTEXT_THRESHOLD, 100)
        self.assertEqual(cfg.AUTO_RELOAD_CONTEXT_THRESHOLD_1M, 500)
        self.assertEqual(cfg.AUTO_RELOAD_IDLE_MIN_CONTEXT, 50)
        self.assertEqual(cfg.AUTO_RELOAD_IDLE_SECONDS, 60)
        self.assertEqual(cfg.AUTO_RELOAD_COOLDOWN_SECONDS, 0)
        self.assertEqual(cfg.AUTO_RELOAD_CHECK_INTERVAL_SECONDS, 5)

    def test_invalid_integer_env_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "COCOON_PORT must be an integer"):
            self.reload_with_env({"COCOON_PORT": "abc"})

    def test_negative_upload_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "COCOON_MAX_UPLOAD_MB must be >= 0"):
            self.reload_with_env({"COCOON_MAX_UPLOAD_MB": "-1"})

    def test_boolean_env_values(self):
        cfg = self.reload_with_env({"COCOON_AUTO_DISMISS_PROMPTS": "off"})
        self.assertFalse(cfg.AUTO_DISMISS_PROMPTS)

        cfg = self.reload_with_env({"COCOON_AUTO_DISMISS_PROMPTS": "yes"})
        self.assertTrue(cfg.AUTO_DISMISS_PROMPTS)

        cfg = self.reload_with_env({"COCOON_AUTO_RELOAD_ENABLED": "1"})
        self.assertTrue(cfg.AUTO_RELOAD_ENABLED)


if __name__ == "__main__":
    unittest.main()
