"""Main window: orb, status, transcript log, and a typed-command fallback."""

from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from jarvis.core import AssistantCore
from jarvis.gui.orb_widget import OrbWidget
from jarvis.gui.theme import DARK_STYLESHEET, STATE_LABELS
from jarvis.gui.worker import AssistantWorker


class MainWindow(QMainWindow):
    def __init__(self, core: AssistantCore) -> None:
        super().__init__()
        self.setWindowTitle("JARVIS")
        self.resize(480, 640)
        self.setStyleSheet(DARK_STYLESHEET)

        self.worker = AssistantWorker(core)
        self.worker.state_changed.connect(self._on_state_changed)
        self.worker.transcript_updated.connect(self._on_transcript)
        self.worker.assistant_reply.connect(self._on_reply)
        self.worker.error.connect(self._on_error)

        self.orb = OrbWidget()

        self.status_label = QLabel(STATE_LABELS["idle"])
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setObjectName("statusLabel")

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("transcriptLog")

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Type a command instead of speaking…")
        self.input_box.returnPressed.connect(self._submit_text)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self._submit_text)

        input_row = QHBoxLayout()
        input_row.addWidget(self.input_box)
        input_row.addWidget(self.send_button)

        layout = QVBoxLayout()
        layout.addWidget(self.orb, 2)
        layout.addWidget(self.status_label)
        layout.addWidget(self.log, 3)
        layout.addLayout(input_row)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.worker.start()

    def _submit_text(self) -> None:
        text = self.input_box.text().strip()
        if not text:
            return
        self.input_box.clear()
        self.worker.submit_text(text)

    def _on_state_changed(self, state: str) -> None:
        self.orb.set_state(state)
        self.status_label.setText(STATE_LABELS.get(state, state.title()))

    def _on_transcript(self, text: str) -> None:
        self.log.append(f"<b>You:</b> {html.escape(text)}")

    def _on_reply(self, text: str) -> None:
        self.log.append(f"<b>JARVIS:</b> {html.escape(text)}")

    def _on_error(self, message: str) -> None:
        self.log.append(f"<span style='color:#ef4444'>Error: {html.escape(message)}</span>")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override naming
        self.worker.stop()
        super().closeEvent(event)
