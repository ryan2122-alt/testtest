import threading
from unittest.mock import MagicMock

from jarvis.core import AssistantCore, EventKind
from jarvis.tts import TTSError


def _make_core(**overrides):
    defaults = dict(
        config=MagicMock(),
        wake_detector=MagicMock(),
        transcriber=MagicMock(),
        brain=MagicMock(),
        tts=MagicMock(),
        mic_stream=MagicMock(),
    )
    defaults.update(overrides)
    core = AssistantCore(**defaults)
    events = []
    core.on_event = lambda event: events.append(event)
    return core, events, defaults


def test_run_forever_full_cycle_emits_expected_events_and_speaks_reply():
    wake_detector = MagicMock()
    wake_detector.listen_for_wake_word.side_effect = [True, False]
    transcriber = MagicMock()
    transcriber.transcribe_command.return_value = "turn on the lights"
    brain = MagicMock()
    brain.converse.return_value = "Done."
    tts = MagicMock()
    mic_stream = MagicMock()

    core, events, _ = _make_core(
        wake_detector=wake_detector, transcriber=transcriber, brain=brain, tts=tts, mic_stream=mic_stream
    )

    core.run_forever(threading.Event())

    kinds = [e.kind for e in events]
    assert kinds == [
        EventKind.WAKE_IDLE,
        EventKind.WAKE_DETECTED,
        EventKind.LISTENING,
        EventKind.TRANSCRIPT_FINAL,
        EventKind.THINKING,
        EventKind.ASSISTANT_REPLY,
        EventKind.SPEAKING,
        EventKind.WAKE_IDLE,
    ]
    brain.converse.assert_called_once_with("turn on the lights")
    tts.speak.assert_called_once_with("Done.")
    mic_stream.start.assert_called_once()
    mic_stream.stop.assert_called_once()


def test_run_forever_ignores_empty_transcript():
    wake_detector = MagicMock()
    wake_detector.listen_for_wake_word.side_effect = [True, False]
    transcriber = MagicMock()
    transcriber.transcribe_command.return_value = ""
    brain = MagicMock()
    tts = MagicMock()

    core, events, _ = _make_core(
        wake_detector=wake_detector, transcriber=transcriber, brain=brain, tts=tts
    )

    core.run_forever(threading.Event())

    assert EventKind.TRANSCRIPT_FINAL not in [e.kind for e in events]
    brain.converse.assert_not_called()
    tts.speak.assert_not_called()


def test_handle_text_command_bypasses_stt():
    brain = MagicMock()
    brain.converse.return_value = "Hi there."
    tts = MagicMock()
    core, events, _ = _make_core(brain=brain, tts=tts)

    core.handle_text_command("hello jarvis")

    brain.converse.assert_called_once_with("hello jarvis")
    tts.speak.assert_called_once_with("Hi there.")
    kinds = [e.kind for e in events]
    assert kinds == [
        EventKind.TRANSCRIPT_FINAL,
        EventKind.THINKING,
        EventKind.ASSISTANT_REPLY,
        EventKind.SPEAKING,
    ]


def test_handle_text_command_ignores_blank_input():
    brain = MagicMock()
    core, events, _ = _make_core(brain=brain)

    core.handle_text_command("   ")

    brain.converse.assert_not_called()
    assert events == []


def test_brain_error_emits_error_and_skips_tts():
    brain = MagicMock()
    brain.converse.side_effect = RuntimeError("boom")
    tts = MagicMock()
    core, events, _ = _make_core(brain=brain, tts=tts)

    core.handle_text_command("do something")

    tts.speak.assert_not_called()
    error_events = [e for e in events if e.kind == EventKind.ERROR]
    assert len(error_events) == 1
    assert "boom" in error_events[0].payload


def test_tts_error_emits_error_event():
    brain = MagicMock()
    brain.converse.return_value = "ok"
    tts = MagicMock()
    tts.speak.side_effect = TTSError("afplay failed")
    core, events, _ = _make_core(brain=brain, tts=tts)

    core.handle_text_command("do something")

    kinds = [e.kind for e in events]
    assert kinds[-1] == EventKind.ERROR
