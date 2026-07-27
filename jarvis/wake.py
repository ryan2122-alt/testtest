"""Offline wake-word ("jarvis") spotting via a grammar-constrained Vosk recognizer.

Restricting the recognizer's vocabulary to just the wake word (plus a
catch-all "[unk]" token) makes always-on listening cheap on CPU and avoids
an open vocabulary competing for probability mass against the one word we
actually care about.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable

logger = logging.getLogger("jarvis.wake")

WAKE_WORD = "jarvis"


def _text_has_wake_word(text: str) -> bool:
    return WAKE_WORD in text.lower().split()


class WakeWordDetector:
    def __init__(
        self,
        model: Any,
        samplerate: int = 16000,
        recognizer_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.model = model
        self.samplerate = samplerate
        self._recognizer_factory = recognizer_factory or self._default_recognizer_factory

    def _default_recognizer_factory(self) -> Any:
        import vosk

        grammar = json.dumps([WAKE_WORD, "[unk]"])
        recognizer = vosk.KaldiRecognizer(self.model, self.samplerate, grammar)
        recognizer.SetWords(False)
        return recognizer

    def listen_for_wake_word(self, mic_stream: Any, stop_flag: threading.Event) -> bool:
        """Block until the wake word is heard or `stop_flag` is set.

        Returns True if the wake word was detected, False if stopped first.
        """
        recognizer = self._recognizer_factory()
        while not stop_flag.is_set():
            chunk = mic_stream.read(timeout=0.5)
            if chunk is None:
                continue

            if recognizer.AcceptWaveform(chunk):
                result = json.loads(recognizer.Result())
                if _text_has_wake_word(result.get("text", "")):
                    logger.info("Wake word detected")
                    return True
            else:
                partial = json.loads(recognizer.PartialResult())
                if _text_has_wake_word(partial.get("partial", "")):
                    logger.info("Wake word detected (partial)")
                    return True
        return False
