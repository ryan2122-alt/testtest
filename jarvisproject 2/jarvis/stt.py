"""Open-vocabulary command transcription with energy-based end-of-speech detection.

No separate VAD dependency: end-of-command is detected by RMS energy on raw
PCM frames dropping below a threshold for `silence_hang_ms`. This is
noise-sensitive by nature (a documented limitation) — `silence_hang_ms` and
the RMS threshold are tunable via config for noisy environments.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable

import numpy as np

logger = logging.getLogger("jarvis.stt")

DEFAULT_SILENCE_RMS_THRESHOLD = 300.0


class CommandTranscriber:
    def __init__(
        self,
        model: Any,
        samplerate: int = 16000,
        silence_hang_ms: int = 800,
        command_timeout_s: float = 8.0,
        silence_rms_threshold: float = DEFAULT_SILENCE_RMS_THRESHOLD,
        recognizer_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.model = model
        self.samplerate = samplerate
        self.silence_hang_ms = silence_hang_ms
        self.command_timeout_s = command_timeout_s
        self.silence_rms_threshold = silence_rms_threshold
        self._recognizer_factory = recognizer_factory or self._default_recognizer_factory

    def _default_recognizer_factory(self) -> Any:
        import vosk

        recognizer = vosk.KaldiRecognizer(self.model, self.samplerate)
        recognizer.SetWords(False)
        return recognizer

    @staticmethod
    def _rms(chunk: bytes) -> float:
        if not chunk:
            return 0.0
        samples = np.frombuffer(chunk, dtype=np.int16)
        if samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))

    def transcribe_command(self, mic_stream: Any, stop_flag: threading.Event) -> str:
        """Record and transcribe one command, returning the final text (may be empty)."""
        recognizer = self._recognizer_factory()
        start = time.monotonic()
        silence_start: float | None = None
        heard_speech = False
        text_parts: list[str] = []

        while not stop_flag.is_set():
            if time.monotonic() - start > self.command_timeout_s:
                logger.info("Command timeout with no complete utterance")
                break

            chunk = mic_stream.read(timeout=0.3)
            if chunk is None:
                continue

            if recognizer.AcceptWaveform(chunk):
                result = json.loads(recognizer.Result())
                text = result.get("text", "")
                if text:
                    text_parts.append(text)
                    heard_speech = True

            is_silent = self._rms(chunk) < self.silence_rms_threshold
            if heard_speech:
                if is_silent:
                    if silence_start is None:
                        silence_start = time.monotonic()
                    elif (time.monotonic() - silence_start) * 1000 >= self.silence_hang_ms:
                        break
                else:
                    silence_start = None

        final = json.loads(recognizer.FinalResult()).get("text", "")
        if final:
            text_parts.append(final)

        transcript = " ".join(part for part in text_parts if part).strip()
        logger.info("Transcribed command: %r", transcript)
        return transcript
