"""Animated orb that reflects the assistant's current state."""

from __future__ import annotations

import math

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from jarvis.gui.theme import STATE_COLORS

FRAME_INTERVAL_MS = 33


class OrbWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self._state = "idle"
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(FRAME_INTERVAL_MS)

    def set_state(self, state: str) -> None:
        self._state = state
        self.update()

    def _tick(self) -> None:
        self._phase += 0.06
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(STATE_COLORS.get(self._state, STATE_COLORS["idle"]))
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        base_radius = min(w, h) * 0.28

        pulse_amplitude = 0.03 if self._state == "idle" else 0.14
        radius = base_radius * (1.0 + pulse_amplitude * math.sin(self._phase))

        glow = QRadialGradient(cx, cy, radius * 1.8)
        glow.setColorAt(0.0, color)
        transparent = QColor(color)
        transparent.setAlpha(0)
        glow.setColorAt(1.0, transparent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            int(cx - radius * 1.8), int(cy - radius * 1.8), int(radius * 3.6), int(radius * 3.6)
        )

        painter.setBrush(color)
        painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))
