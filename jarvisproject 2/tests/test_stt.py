import json
import threading

import numpy as np
import pytest

from jarvis.stt import CommandTranscriber


class FakeMicStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def read(self, timeout=None):
        return self._chunks.pop(0) if self._chunks else None


class FakeSTTRecognizer:
    def __init__(self, accept_pattern, result_text=""):
        self._pattern = list(accept_pattern)
        self._result_text = result_text

    def AcceptWaveform(self, chunk):
        return self._pattern.pop(0) if self._pattern else False

    def Result(self):
        return json.dumps({"text": self._result_text})

    def FinalResult(self):
        return json.dumps({"text": ""})

    def SetWords(self, value):
        pass


def _pcm_chunk(amplitude: int, n_samples: int = 160) -> bytes:
    return (np.full(n_samples, amplitude, dtype=np.int16)).tobytes()


def _fake_clock(increment: float):
    state = {"t": 0.0}

    def tick():
        state["t"] += increment
        return state["t"]

    return tick


def test_transcribe_command_stops_after_trailing_silence(monkeypatch):
    monkeypatch.setattr("jarvis.stt.time.monotonic", _fake_clock(0.05))

    chunks = [
        _pcm_chunk(5000),  # speech, loud
        _pcm_chunk(5000),  # speech, loud -> AcceptWaveform True with final text
        _pcm_chunk(0),  # silence
        _pcm_chunk(0),  # silence -> should trip the hang timer
    ]
    mic = FakeMicStream(chunks)
    recognizer = FakeSTTRecognizer(
        accept_pattern=[False, True, False, False], result_text="hello jarvis"
    )
    transcriber = CommandTranscriber(
        model=None,
        silence_hang_ms=1,
        command_timeout_s=10,
        silence_rms_threshold=1000,
        recognizer_factory=lambda: recognizer,
    )

    text = transcriber.transcribe_command(mic, threading.Event())

    assert "hello jarvis" in text


def test_transcribe_command_times_out_with_no_speech(monkeypatch):
    monkeypatch.setattr("jarvis.stt.time.monotonic", _fake_clock(0.1))

    mic = FakeMicStream([_pcm_chunk(0)] * 5)
    recognizer = FakeSTTRecognizer(accept_pattern=[False] * 5, result_text="")
    transcriber = CommandTranscriber(
        model=None,
        silence_hang_ms=100_000,
        command_timeout_s=0.15,
        recognizer_factory=lambda: recognizer,
    )

    text = transcriber.transcribe_command(mic, threading.Event())

    assert text == ""


def test_transcribe_command_respects_stop_flag():
    mic = FakeMicStream([_pcm_chunk(0)] * 3)
    recognizer = FakeSTTRecognizer(accept_pattern=[False] * 3, result_text="")
    transcriber = CommandTranscriber(
        model=None, command_timeout_s=999, recognizer_factory=lambda: recognizer
    )
    stop_flag = threading.Event()
    stop_flag.set()

    text = transcriber.transcribe_command(mic, stop_flag)

    assert text == ""


@pytest.mark.parametrize(
    ("amplitude", "expected_low"),
    [(0, True), (32000, False)],
)
def test_rms_reflects_amplitude(amplitude, expected_low):
    rms = CommandTranscriber._rms(_pcm_chunk(amplitude))
    assert (rms < 1000) == expected_low
