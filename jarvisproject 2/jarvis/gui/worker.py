"""Bridges the UI-agnostic AssistantCore onto a background thread with Qt signals.

Note on threading approach: the voice loop (`AssistantCore.run_forever`)
blocks essentially forever. Running it as a slot connected to a QThread's
`started` signal would starve that thread's event loop, since Qt processes
queued cross-thread slot calls (like a GUI-typed command) one event at a
time and can't service a second one while the first handler never returns.
Instead this uses a plain `threading.Thread` for the voice loop and relies
on the fact that Qt signal emission is thread-safe regardless of whether
the emitting thread runs a Qt event loop: `Signal.emit()` from any thread
is safely queued onto the *receiver's* thread (the GUI thread here, which
is always pumping events via `QApplication.exec()`). GUI -> worker text
submissions are dispatched on their own short-lived thread and serialized
against the voice loop via `AssistantCore`'s internal turn lock.
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Signal

from jarvis.core import AssistantCore, AssistantEvent, EventKind

logger = logging.getLogger("jarvis.gui.worker")

_STATE_EVENTS = {
    EventKind.WAKE_IDLE: "idle",
    EventKind.WAKE_DETECTED: "wake_detected",
    EventKind.LISTENING: "listening",
    EventKind.THINKING: "thinking",
    EventKind.SPEAKING: "speaking",
}


class AssistantWorker(QObject):
    state_changed = Signal(str)
    transcript_updated = Signal(str)
    assistant_reply = Signal(str)
    error = Signal(str)

    def __init__(self, core: AssistantCore) -> None:
        super().__init__()
        self._core = core
        self._core.on_event = self._on_event
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _on_event(self, event: AssistantEvent) -> None:
        state = _STATE_EVENTS.get(event.kind)
        if state is not None:
            self.state_changed.emit(state)
        if event.kind == EventKind.TRANSCRIPT_FINAL:
            self.transcript_updated.emit(event.payload)
        elif event.kind == EventKind.ASSISTANT_REPLY:
            self.assistant_reply.emit(event.payload)
        elif event.kind == EventKind.ERROR:
            self.error.emit(event.payload)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._core.run_forever, args=(self._stop_event,), daemon=True, name="jarvis-voice-loop"
        )
        self._thread.start()

    def submit_text(self, text: str) -> None:
        threading.Thread(
            target=self._core.handle_text_command, args=(text,), daemon=True, name="jarvis-text-command"
        ).start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
