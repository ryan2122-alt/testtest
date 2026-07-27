"""UI-agnostic assistant state machine: wake word -> command -> brain -> speech.

Deliberately has zero PySide6/Qt imports so it can run headless (`--cli`) or
be wrapped by a Qt worker thread (`jarvis.gui.worker.AssistantWorker`) that
re-emits `on_event` calls as Qt signals. All collaborators are injected so
tests can substitute fakes for the mic, Vosk recognizers, Groq client, and
TTS/playback.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable

from jarvis.brain import Brain
from jarvis.config import Config
from jarvis.stt import CommandTranscriber
from jarvis.tts import ElevenLabsTTS, TTSError
from jarvis.wake import WakeWordDetector

logger = logging.getLogger("jarvis.core")


class EventKind(Enum):
    WAKE_IDLE = auto()
    WAKE_DETECTED = auto()
    LISTENING = auto()
    TRANSCRIPT_FINAL = auto()
    THINKING = auto()
    ASSISTANT_REPLY = auto()
    SPEAKING = auto()
    ERROR = auto()


@dataclass(frozen=True)
class AssistantEvent:
    kind: EventKind
    payload: str = ""


OnEvent = Callable[[AssistantEvent], None]


class AssistantCore:
    def __init__(
        self,
        config: Config,
        wake_detector: WakeWordDetector,
        transcriber: CommandTranscriber,
        brain: Brain,
        tts: ElevenLabsTTS,
        mic_stream: Any,
        on_event: OnEvent | None = None,
    ) -> None:
        self.config = config
        self.wake_detector = wake_detector
        self.transcriber = transcriber
        self.brain = brain
        self.tts = tts
        self.mic_stream = mic_stream
        self.on_event = on_event or (lambda event: None)
        # Serializes _handle_transcript so a voice command and a GUI-typed
        # command can never call Brain.converse concurrently and corrupt
        # its shared message history.
        self._turn_lock = threading.Lock()

    def _emit(self, kind: EventKind, payload: str = "") -> None:
        try:
            self.on_event(AssistantEvent(kind, payload))
        except Exception:  # noqa: BLE001 - a buggy UI callback must not kill the voice loop
            logger.exception("on_event callback raised")

    def run_forever(self, stop_flag: threading.Event) -> None:
        """Blocking loop: wait for the wake word, handle a command, repeat.

        Runs until `stop_flag` is set. Intended to run on a dedicated thread
        (or the main thread in `--cli` mode) — never on the Qt GUI thread.
        """
        self.mic_stream.start()
        try:
            while not stop_flag.is_set():
                self._emit(EventKind.WAKE_IDLE)
                detected = self.wake_detector.listen_for_wake_word(self.mic_stream, stop_flag)
                if not detected:
                    break  # stop_flag was set while waiting

                self._emit(EventKind.WAKE_DETECTED)
                self._emit(EventKind.LISTENING)
                transcript = self.transcriber.transcribe_command(self.mic_stream, stop_flag)
                if stop_flag.is_set():
                    break
                if not transcript:
                    logger.info("No command heard after wake word; returning to idle")
                    continue

                self._emit(EventKind.TRANSCRIPT_FINAL, transcript)
                self._handle_transcript(transcript)
        finally:
            self.mic_stream.stop()

    def handle_text_command(self, text: str) -> None:
        """GUI text-input fallback: skip STT, feed text straight to the brain."""
        text = text.strip()
        if not text:
            return
        self._emit(EventKind.TRANSCRIPT_FINAL, text)
        self._handle_transcript(text)

    def _handle_transcript(self, transcript: str) -> None:
        with self._turn_lock:
            self._emit(EventKind.THINKING)
            try:
                reply = self.brain.converse(transcript)
            except Exception as exc:  # noqa: BLE001 - a brain bug must not kill the voice loop
                logger.exception("Unexpected brain error")
                self._emit(EventKind.ERROR, str(exc))
                return

            self._emit(EventKind.ASSISTANT_REPLY, reply)
            self._emit(EventKind.SPEAKING, reply)
            try:
                self.tts.speak(reply)
            except TTSError as exc:
                logger.error("TTS error: %s", exc)
                self._emit(EventKind.ERROR, str(exc))
