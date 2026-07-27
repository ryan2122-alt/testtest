import json
import threading

from jarvis.wake import WakeWordDetector, _text_has_wake_word


class FakeMicStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def read(self, timeout=None):
        return self._chunks.pop(0) if self._chunks else None


class FakeMicStreamThatStops(FakeMicStream):
    """Sets stop_flag once its canned chunks are exhausted, to avoid infinite loops."""

    def __init__(self, chunks, stop_flag):
        super().__init__(chunks)
        self._stop_flag = stop_flag

    def read(self, timeout=None):
        chunk = super().read(timeout)
        if chunk is None:
            self._stop_flag.set()
        return chunk


class FakeWakeRecognizer:
    def __init__(self, accept_pattern, result_text="", partial_text=""):
        self._pattern = list(accept_pattern)
        self._result_text = result_text
        self._partial_text = partial_text

    def AcceptWaveform(self, chunk):
        return self._pattern.pop(0) if self._pattern else False

    def Result(self):
        return json.dumps({"text": self._result_text})

    def PartialResult(self):
        return json.dumps({"partial": self._partial_text})

    def SetWords(self, value):
        pass


def test_text_has_wake_word_matches_whole_word_only():
    assert _text_has_wake_word("hey jarvis how are you")
    assert not _text_has_wake_word("jarvison is not the wake word")
    assert not _text_has_wake_word("")


def test_wake_word_grammar_only_contains_wake_word_and_unk():
    # Inspect the grammar JSON the default factory would build, without
    # loading a real Vosk model — patch vosk.KaldiRecognizer to capture args.
    detector = WakeWordDetector(model=object())
    captured = {}

    class _CapturingRecognizer:
        def __init__(self, model, samplerate, grammar):
            captured["grammar"] = json.loads(grammar)

        def SetWords(self, value):
            pass

    import sys
    import types

    fake_vosk = types.SimpleNamespace(KaldiRecognizer=_CapturingRecognizer)
    sys.modules["vosk"] = fake_vosk
    try:
        detector._default_recognizer_factory()
    finally:
        del sys.modules["vosk"]

    assert captured["grammar"] == ["jarvis", "[unk]"]


def test_listen_for_wake_word_detects_via_final_result():
    recognizer = FakeWakeRecognizer(accept_pattern=[False, True], result_text="hey jarvis")
    mic = FakeMicStream([b"chunk0", b"chunk1"])
    detector = WakeWordDetector(model=None, recognizer_factory=lambda: recognizer)

    assert detector.listen_for_wake_word(mic, threading.Event()) is True


def test_listen_for_wake_word_detects_via_partial_result():
    recognizer = FakeWakeRecognizer(accept_pattern=[False], partial_text="jarvis")
    mic = FakeMicStream([b"chunk0"])
    detector = WakeWordDetector(model=None, recognizer_factory=lambda: recognizer)

    assert detector.listen_for_wake_word(mic, threading.Event()) is True


def test_listen_for_wake_word_returns_false_when_stopped():
    recognizer = FakeWakeRecognizer(accept_pattern=[False, False])
    stop_flag = threading.Event()
    mic = FakeMicStreamThatStops([b"c0", b"c1"], stop_flag)
    detector = WakeWordDetector(model=None, recognizer_factory=lambda: recognizer)

    assert detector.listen_for_wake_word(mic, stop_flag) is False
