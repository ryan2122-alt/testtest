"""ElevenLabs text-to-speech, played locally via macOS `afplay`.

Fetch-full-then-play rather than streaming PCM: `afplay` handles MP3
natively with zero extra audio-output dependency, and for short spoken
replies (the system prompt asks for 1-3 sentences) the added latency vs.
true streaming is small relative to the rest of the round trip.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.tts")

SCRATCH_DIR = Path(tempfile.gettempdir()) / "jarvis-tts"


class TTSError(RuntimeError):
    """Raised when synthesis or playback fails."""


class ElevenLabsTTS:
    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model_id: str = "eleven_turbo_v2_5",
        client: Any = None,
    ) -> None:
        self.voice_id = voice_id
        self.model_id = model_id
        self._client = client or self._build_client(api_key)
        SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _build_client(api_key: str) -> Any:
        from elevenlabs.client import ElevenLabs

        return ElevenLabs(api_key=api_key)

    def _synthesize(self, text: str) -> bytes:
        try:
            audio = self._client.text_to_speech.convert(
                voice_id=self.voice_id,
                model_id=self.model_id,
                text=text,
                output_format="mp3_44100_128",
            )
        except Exception as exc:  # noqa: BLE001 - SDK errors (quota/rate-limit/network)
            raise TTSError(f"ElevenLabs synthesis failed: {exc}") from exc

        if isinstance(audio, (bytes, bytearray)):
            return bytes(audio)
        # The SDK may return an iterator/generator of byte chunks.
        return b"".join(audio)

    def speak(self, text: str) -> None:
        """Synthesize `text` and play it back, blocking until playback finishes."""
        if not text.strip():
            return

        audio_bytes = self._synthesize(text)

        fd, path_str = tempfile.mkstemp(suffix=".mp3", dir=SCRATCH_DIR)
        path = Path(path_str)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(audio_bytes)
            result = subprocess.run(["afplay", str(path)], capture_output=True, text=True)
            if result.returncode != 0:
                raise TTSError(f"afplay failed: {result.stderr.strip()}")
        finally:
            path.unlink(missing_ok=True)
