import subprocess
from unittest.mock import MagicMock, patch

import pytest

from jarvis.tts import ElevenLabsTTS, TTSError


def _tts_with_fake_client(convert_return):
    client = MagicMock()
    client.text_to_speech.convert.return_value = convert_return
    return ElevenLabsTTS(api_key="key", voice_id="voice", client=client), client


@patch("jarvis.tts.subprocess.run")
def test_speak_plays_synthesized_audio_via_afplay(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    tts, client = _tts_with_fake_client(convert_return=b"fake-mp3-bytes")

    tts.speak("Hello there.")

    client.text_to_speech.convert.assert_called_once()
    kwargs = client.text_to_speech.convert.call_args.kwargs
    assert kwargs["voice_id"] == "voice"
    assert kwargs["text"] == "Hello there."

    mock_run.assert_called_once()
    played_path = mock_run.call_args[0][0][1]
    assert played_path.endswith(".mp3")


@patch("jarvis.tts.subprocess.run")
def test_speak_joins_iterator_of_chunks(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    tts, client = _tts_with_fake_client(convert_return=iter([b"chunk1", b"chunk2"]))

    tts.speak("Hi")

    mock_run.assert_called_once()


def test_speak_skips_empty_text():
    tts, client = _tts_with_fake_client(convert_return=b"unused")

    tts.speak("   ")

    client.text_to_speech.convert.assert_not_called()


def test_synthesis_failure_raises_tts_error():
    client = MagicMock()
    client.text_to_speech.convert.side_effect = RuntimeError("quota exceeded")
    tts = ElevenLabsTTS(api_key="key", voice_id="voice", client=client)

    with pytest.raises(TTSError, match="quota exceeded"):
        tts.speak("hello")


@patch("jarvis.tts.subprocess.run")
def test_playback_failure_raises_tts_error_and_cleans_up_temp_file(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stderr="device busy")
    tts, client = _tts_with_fake_client(convert_return=b"fake-mp3-bytes")

    with pytest.raises(TTSError, match="device busy"):
        tts.speak("hello")

    played_path = mock_run.call_args[0][0][1]
    from pathlib import Path

    assert not Path(played_path).exists()
