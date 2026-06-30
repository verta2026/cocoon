import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import bridge.tts as tts


class TtsTest(unittest.TestCase):
    def test_synthesize_rejects_text_over_configured_limit(self):
        with patch("bridge.tts.TTS_MAX_TEXT_CHARS", 3):
            with self.assertRaises(HTTPException) as ctx:
                tts.synthesize_tts(Path("."), "abcd")

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("max 3 chars", ctx.exception.detail)

    def test_cleanup_audio_files_keeps_newest_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old.mp3"
            mid = root / "mid.mp3"
            new = root / "new.mp3"
            for idx, path in enumerate((old, mid, new)):
                path.write_bytes(b"x")
                ts = time.time() + idx
                os.utime(path, (ts, ts))

            tts._cleanup_audio_files(root, max_files=2)

            self.assertFalse(old.exists())
            self.assertTrue(mid.exists())
            self.assertTrue(new.exists())

    def test_serve_tts_audio_rejects_traversal_and_wrong_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_id = "a" * 16
            (root / f"{audio_id}.txt").write_text("not audio", encoding="utf-8")

            with self.assertRaises(HTTPException) as invalid:
                tts.serve_tts_audio(root, "../" + audio_id + ".mp3")
            self.assertEqual(invalid.exception.status_code, 400)

            with self.assertRaises(HTTPException) as wrong_suffix:
                tts.serve_tts_audio(root, audio_id + ".txt")
            self.assertEqual(wrong_suffix.exception.status_code, 400)

    def test_serve_tts_audio_sets_private_cache_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_name = "b" * 16 + ".mp3"
            (root / audio_name).write_bytes(b"mp3")

            response = tts.serve_tts_audio(root, audio_name)

            self.assertEqual(response.headers["cache-control"], "private, max-age=86400")


if __name__ == "__main__":
    unittest.main()
