"""Headless Qt smoke test. Requires QT_QPA_PLATFORM=offscreen (set in conftest)."""

import threading
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")

from jarvis.core import AssistantCore  # noqa: E402


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _blocking_wake_detector():
    detector = MagicMock()

    def listen(mic, stop_flag):
        stop_flag.wait()
        return False

    detector.listen_for_wake_word.side_effect = listen
    return detector


def test_main_window_constructs_and_shows(qapp):
    from jarvis.gui.main_window import MainWindow

    core = AssistantCore(
        config=MagicMock(),
        wake_detector=_blocking_wake_detector(),
        transcriber=MagicMock(),
        brain=MagicMock(),
        tts=MagicMock(),
        mic_stream=MagicMock(),
    )

    window = MainWindow(core)
    window.show()

    assert window.windowTitle() == "JARVIS"
    assert window.isVisible()

    window.worker.stop()


def test_orb_widget_paints_without_raising(qapp):
    from jarvis.gui.orb_widget import OrbWidget

    orb = OrbWidget()
    orb.resize(200, 200)
    orb.set_state("listening")
    orb.repaint()  # forces paintEvent synchronously
