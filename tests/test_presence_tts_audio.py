import os
import tempfile
import time
import unittest
from pathlib import Path

from presence.tts_audio import (
    audio_file_path,
    cleanup_audio_files,
    is_valid_audio_id,
    latest_meta,
    make_audio_id,
    normalize_required_text,
    public_meta,
    validate_tts_request,
)


class PresenceTtsAudioTests(unittest.TestCase):
    def test_validate_tts_request_trims_and_validates(self):
        self.assertEqual(
            validate_tts_request(" hello ", "happy", max_text_chars=10, allowed_emotions={"happy"}),
            ("hello", "happy"),
        )
        with self.assertRaisesRegex(ValueError, "missing text"):
            validate_tts_request("   ", None, max_text_chars=10, allowed_emotions=set())
        with self.assertRaisesRegex(ValueError, "text too long"):
            validate_tts_request("abcd", None, max_text_chars=3, allowed_emotions=set())
        with self.assertRaisesRegex(ValueError, "invalid emotion"):
            validate_tts_request("ok", "sad", max_text_chars=10, allowed_emotions={"happy"})

    def test_normalize_required_text_only_requires_text(self):
        self.assertEqual(normalize_required_text(" hello "), "hello")
        with self.assertRaisesRegex(ValueError, "missing text"):
            normalize_required_text("")

    def test_make_audio_id_is_stable_for_supplied_time(self):
        first = make_audio_id("hello", "happy", now=1.25)
        second = make_audio_id("hello", "happy", now=1.25)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 20)
        self.assertNotEqual(first, make_audio_id("hello", None, now=1.25))

    def test_audio_file_path_appends_mp3(self):
        self.assertEqual(audio_file_path("/tmp/tts", "abc"), os.path.join("/tmp/tts", "abc.mp3"))

    def test_public_meta_hides_missing_url(self):
        self.assertEqual(
            public_meta({"id": "abc", "text": "hi", "bytes": 5}),
            {
                "id": "abc",
                "url": "/tts/audio/abc.mp3",
                "text": "hi",
                "emotion": "",
                "created_at": "",
                "source": "",
                "bytes": 5,
            },
        )
        self.assertEqual(public_meta({})["url"], "")

    def test_latest_meta_builds_record(self):
        self.assertEqual(
            latest_meta(audio_id="abc", text="hi", emotion=None, source="test", size=3, created_at="now"),
            {"id": "abc", "text": "hi", "emotion": "", "source": "test", "bytes": 3, "created_at": "now"},
        )

    def test_cleanup_audio_files_keeps_newest_mp3_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old.mp3"
            keep = root / "keep.mp3"
            newer = root / "newer.mp3"
            ignored = root / "note.txt"
            old.write_bytes(b"old")
            keep.write_bytes(b"keep")
            newer.write_bytes(b"new")
            ignored.write_text("ignore", encoding="utf-8")
            now = time.time()
            os.utime(old, (now - 30, now - 30))
            os.utime(keep, (now - 20, now - 20))
            os.utime(newer, (now - 10, now - 10))

            cleanup_audio_files(str(root), max_files=2)

            self.assertFalse(old.exists())
            self.assertTrue(keep.exists())
            self.assertTrue(newer.exists())
            self.assertTrue(ignored.exists())

    def test_is_valid_audio_id_rejects_empty_and_path_like_ids(self):
        self.assertFalse(is_valid_audio_id(""))
        self.assertFalse(is_valid_audio_id("../a"))
        self.assertFalse(is_valid_audio_id("a\\b"))
        self.assertTrue(is_valid_audio_id("abc123"))


if __name__ == "__main__":
    unittest.main()
