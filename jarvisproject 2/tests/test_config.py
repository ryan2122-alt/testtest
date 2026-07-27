from pathlib import Path

import pytest

from jarvis.config import ConfigError, load_config

_ENV_KEYS = (
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "ELEVENLABS_API_KEY",
    "VOICE_ID",
    "ELEVENLABS_MODEL_ID",
    "VOSK_MODEL_PATH",
    "JARVIS_ALLOWED_DIRS",
    "COMMAND_TIMEOUT_S",
    "SILENCE_HANG_MS",
    "LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Isolate each test from the real process env and from prior tests.

    load_config() uses load_dotenv(..., override=False), so once a key is
    set in os.environ it survives across tests unless explicitly cleared.
    """
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _write_env(tmp_path: Path, content: str) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text(content)
    return env_file


def test_missing_required_key_raises_config_error(tmp_path):
    env_file = _write_env(tmp_path, "GROQ_API_KEY=abc\n")

    with pytest.raises(ConfigError, match="ELEVENLABS_API_KEY"):
        load_config(env_file)


def test_loads_full_config(tmp_path):
    env_file = _write_env(
        tmp_path,
        "GROQ_API_KEY=gsk_test\n"
        "ELEVENLABS_API_KEY=el_test\n"
        "VOICE_ID=voice123\n"
        f"JARVIS_ALLOWED_DIRS={tmp_path}\n",
    )

    config = load_config(env_file)

    assert config.groq_api_key == "gsk_test"
    assert config.elevenlabs_api_key == "el_test"
    assert config.voice_id == "voice123"
    assert config.allowed_dirs == (tmp_path.resolve(),)
    assert config.groq_model  # has a default
    assert config.command_timeout_s == 8.0


def test_allowed_dirs_requires_at_least_one(tmp_path):
    env_file = _write_env(
        tmp_path,
        "GROQ_API_KEY=gsk_test\nELEVENLABS_API_KEY=el_test\nVOICE_ID=v\nJARVIS_ALLOWED_DIRS=\n",
    )

    with pytest.raises(ConfigError, match="ALLOWED_DIRS"):
        load_config(env_file)
