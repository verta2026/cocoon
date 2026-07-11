import json
import tempfile
import unittest
from pathlib import Path

from presence.settings_file import read_text_file, validate_json_document, write_text_file


class PresenceSettingsFileTests(unittest.TestCase):
    def test_read_and_write_text_file_use_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"

            write_text_file(str(path), '{"label": "cafe"}')

            self.assertEqual(read_text_file(str(path)), '{"label": "cafe"}')

    def test_validate_json_document_accepts_valid_json(self):
        self.assertIsNone(validate_json_document('{"model": "test"}'))

    def test_validate_json_document_raises_for_invalid_json(self):
        with self.assertRaises(json.JSONDecodeError):
            validate_json_document("{bad")


if __name__ == "__main__":
    unittest.main()
