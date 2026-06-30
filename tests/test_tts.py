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


if __name__ == "__main__":
    unittest.main()
