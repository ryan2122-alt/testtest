"""Continuous microphone capture, bridged into a thread-safe queue.

A single stream is opened once and shared across wake-word detection and
command transcription (only the Vosk recognizer/interpretation changes
between states) — reopening the CoreAudio device on every state transition
would add noticeable latency on macOS.
"""

from __future__ import annotations

import logging
import queue
from typing import Any

logger = logging.getLogger("jarvis.audio_input")

DEFAULT_SAMPLERATE = 16000
DEFAULT_BLOCKSIZE = 8000  # ~0.5s at 16kHz, keeps shutdown/stop latency low


class MicStream:
    """Wraps a sounddevice RawInputStream, pushing raw PCM chunks onto a queue."""

    def __init__(
        self,
        samplerate: int = DEFAULT_SAMPLERATE,
        blocksize: int = DEFAULT_BLOCKSIZE,
        device: int | str | None = None,
    ) -> None:
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.device = device
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._stream: Any = None

    def _callback(self, indata: Any, frames: int, time_info: Any, status: Any) -> None:
        if status:
            logger.debug("audio input status: %s", status)
        self._queue.put(bytes(indata))

    def start(self) -> None:
        import sounddevice as sd

        self._stream = sd.RawInputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            device=self.device,
            dtype="int16",
            channels=1,
            callback=self._callback,
        )
        self._stream.start()
        logger.info("Mic stream started (samplerate=%d, blocksize=%d)", self.samplerate, self.blocksize)

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            logger.info("Mic stream stopped")

    def read(self, timeout: float | None = None) -> bytes | None:
        """Return the next raw PCM chunk, or None if `timeout` elapses first."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def __enter__(self) -> "MicStream":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()


def list_devices() -> str:
    """Human-readable listing of available audio input devices."""
    import sounddevice as sd

    return str(sd.query_devices())
