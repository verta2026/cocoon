import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace

from bridge.tts_routes import TtsRequest, register_tts_routes


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._decorator("GET", path)

    def post(self, path):
        return self._decorator("POST", path)

    def _decorator(self, method, path):
        def decorate(func):
            self.routes[(method, path)] = func
            return func
        return decorate


class TtsRoutesTest(unittest.TestCase):
    def test_registers_tts_routes(self):
        app = FakeApp()
        calls = []

        def verify_token(request):
            calls.append(("verify", request.name))

        # Real signature is (request, expected_secret, query_token). The audio
        # route must pass the server's own bridge_token into the secret slot —
        # never the client-supplied ?token=, which was the auth-bypass.
        def verify_media_token(request, expected, token=None):
            calls.append(("media", request.name, expected, token))

        def latest_tts(tts_dir):
            return {"latest": str(tts_dir)}

        def synthesize_tts(tts_dir, text, *, emotion=None, source="frontend"):
            return {"tts_dir": str(tts_dir), "text": text, "emotion": emotion, "source": source}

        def serve_tts_audio(tts_dir, audio_name):
            return {"tts_dir": str(tts_dir), "audio": audio_name}

        register_tts_routes(
            app,
            verify_token=verify_token,
            verify_media_token=verify_media_token,
            latest_tts=latest_tts,
            synthesize_tts=synthesize_tts,
            serve_tts_audio=serve_tts_audio,
            tts_dir=Path("/tmp/tts"),
            bridge_token="server-secret",
        )

        latest = asyncio.run(app.routes[("GET", "/tts/latest")](SimpleNamespace(name="latest")))
        spoken = asyncio.run(
            app.routes[("POST", "/tts/say")](
                TtsRequest(text="hello", emotion="happy", source="test"),
                SimpleNamespace(name="say"),
            )
        )
        audio = asyncio.run(
            app.routes[("GET", "/tts/audio/{audio_name}")](
                "a" * 16 + ".mp3",
                SimpleNamespace(name="audio"),
                token="secret",
            )
        )

        tts_dir_text = str(Path("/tmp/tts"))
        self.assertEqual(latest, {"latest": tts_dir_text})
        self.assertEqual(spoken, {"tts_dir": tts_dir_text, "text": "hello", "emotion": "happy", "source": "test"})
        self.assertEqual(audio, {"tts_dir": tts_dir_text, "audio": "a" * 16 + ".mp3"})
        self.assertEqual(calls, [
            ("verify", "latest"),
            ("verify", "say"),
            # secret slot is the server bridge_token, not the client ?token=secret
            ("media", "audio", "server-secret", "secret"),
        ])


if __name__ == "__main__":
    unittest.main()
