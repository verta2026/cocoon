import tempfile
import unittest
from pathlib import Path

from bridge.json_store import write_json_atomic
from bridge.extensions import list_extensions, normalize_extension


class ExtensionsTest(unittest.TestCase):
    def test_normalize_extension_keeps_safe_public_shape(self):
        item = normalize_extension(
            {
                "id": "docs.link",
                "title": "Docs",
                "href": "/docs",
                "kind": "unknown",
                "description": "Open docs",
            }
        )

        self.assertEqual(
            item,
            {
                "id": "docs.link",
                "title": "Docs",
                "href": "/docs",
                "kind": "link",
                "enabled": True,
                "description": "Open docs",
            },
        )

    def test_rejects_invalid_ids_and_unsafe_hrefs(self):
        self.assertIsNone(normalize_extension({"id": "../bad", "title": "Bad", "href": "/bad"}))
        self.assertIsNone(normalize_extension({"id": "bad", "title": "Bad", "href": "javascript:alert(1)"}))

    def test_list_extensions_filters_disabled_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "extensions.json"
            write_json_atomic(
                path,
                {
                    "extensions": [
                        {"id": "one", "title": "One", "href": "/one"},
                        {"id": "one", "title": "Duplicate", "href": "/duplicate"},
                        {"id": "two", "title": "Two", "href": "https://example.com", "enabled": False},
                        {"id": "three", "title": "Three", "href": "https://example.com", "kind": "plugin"},
                    ]
                },
            )

            items = list_extensions(path)

            self.assertEqual([item["id"] for item in items], ["one", "three"])
            self.assertEqual(items[1]["kind"], "plugin")


if __name__ == "__main__":
    unittest.main()
