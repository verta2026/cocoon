import tempfile
import unittest
from pathlib import Path

from presence.static_pages import read_static_page, static_page_path


class PresenceStaticPagesTest(unittest.TestCase):
    def test_read_static_page_serves_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page.html").write_text("<h1>ok</h1>", encoding="utf-8")

            status, body, content_type = read_static_page(
                "/page.html",
                page_map={"/page.html": "page.html"},
                root_dir=root,
            )

            self.assertEqual(status, 200)
            self.assertEqual(body, b"<h1>ok</h1>")
            self.assertEqual(content_type, "text/html; charset=utf-8")

    def test_read_static_page_returns_none_for_unmapped_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(read_static_page("/missing.html", page_map={}, root_dir=Path(tmp)))

    def test_read_static_page_returns_404_for_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                read_static_page("/page.html", page_map={"/page.html": "page.html"}, root_dir=Path(tmp)),
                (404, b'{"error": "not found"}', "application/json"),
            )

    def test_static_page_path_rejects_escape_from_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(
                static_page_path("/secret.html", page_map={"/secret.html": "../secret.html"}, root_dir=Path(tmp))
            )


if __name__ == "__main__":
    unittest.main()
