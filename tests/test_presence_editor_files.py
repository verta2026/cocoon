import unittest

from presence.editor_files import (
    download_content_type,
    download_filename_header,
    is_safe_relative_path,
    with_utf8_bom_if_needed,
)


class PresenceEditorFilesTests(unittest.TestCase):
    def test_is_safe_relative_path_rejects_parent_and_blocked_entries(self):
        blocked_prefixes = {"private", "memory/vector_index"}
        blocked_files = {".vapid.json"}

        self.assertFalse(is_safe_relative_path("../secret", blocked_prefixes=blocked_prefixes))
        self.assertFalse(is_safe_relative_path("folder/..hidden", blocked_prefixes=blocked_prefixes))
        self.assertFalse(is_safe_relative_path("private/note.md", blocked_prefixes=blocked_prefixes))
        self.assertFalse(is_safe_relative_path("safe/.vapid.json", blocked_files=blocked_files))
        self.assertTrue(
            is_safe_relative_path(
                "safe/note.md",
                blocked_prefixes=blocked_prefixes,
                blocked_files=blocked_files,
            )
        )

    def test_download_filename_header_uses_safe_ascii_fallback_and_encoded_name(self):
        header = download_filename_header('猫"note.md')

        self.assertIn('filename="_note.md"', header)
        self.assertIn("filename*=UTF-8''%E7%8C%AB%22note.md", header)

    def test_download_filename_header_handles_hidden_or_non_ascii_only_name(self):
        self.assertIn('filename="download"', download_filename_header(".env"))
        self.assertIn('filename="download.md"', download_filename_header("猫.md"))

    def test_download_content_type_adds_utf8_to_text_like_files(self):
        self.assertEqual(download_content_type("note.md"), "text/markdown; charset=utf-8")
        self.assertEqual(download_content_type("settings.json"), "application/json; charset=utf-8")
        self.assertEqual(download_content_type("audio.mp3"), "audio/mpeg")

    def test_with_utf8_bom_if_needed_only_prefixes_configured_extensions(self):
        self.assertEqual(with_utf8_bom_if_needed(b"abc", "note.md", {".md"}), b"\xef\xbb\xbfabc")
        self.assertEqual(
            with_utf8_bom_if_needed(b"\xef\xbb\xbfabc", "note.md", {".md"}),
            b"\xef\xbb\xbfabc",
        )
        self.assertEqual(with_utf8_bom_if_needed(b"abc", "note.json", {".md"}), b"abc")


if __name__ == "__main__":
    unittest.main()
