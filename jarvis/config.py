"""Central configuration: loads secrets and tunables from a local .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    groq_api_key: str
    groq_model: str

    elevenlabs_api_key: str
    voice_id: str
    elevenlabs_model_id: str

    vosk_model_path: Path

    allowed_dirs: tuple[Path, ...]

    command_timeout_s: float
    silence_hang_ms: int
    log_level: str

    log_dir: Path = field(default_factory=lambda: Path("logs"))


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(
            f"Missing required environment variable '{name}'. "
            "Copy .env.example to .env and fill in your keys."
        )
    return value


def _parse_allowed_dirs(raw: str) -> tuple[Path, ...]:
    dirs = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        dirs.append(Path(part).expanduser().resolve())
    if not dirs:
        raise ConfigError(
            "JARVIS_ALLOWED_DIRS must list at least one directory the file "
            "tools are permitted to touch."
        )
    return tuple(dirs)


def load_config(env_file: str | Path = ".env") -> Config:
    """Load configuration from the environment / a .env file.

    Raises ConfigError with a clear, actionable message if anything
    required is missing.
    """
    load_dotenv(dotenv_path=env_file, override=False)

    allowed_dirs_raw = os.getenv(
        "JARVIS_ALLOWED_DIRS", "~/Documents,~/Desktop,~/Downloads"
    )

    return Config(
        groq_api_key=_require("GROQ_API_KEY"),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        elevenlabs_api_key=_require("ELEVENLABS_API_KEY"),
        voice_id=_require("VOICE_ID"),
        elevenlabs_model_id=os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5"),
        vosk_model_path=Path(
            os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15")
        ),
        allowed_dirs=_parse_allowed_dirs(allowed_dirs_raw),
        command_timeout_s=float(os.getenv("COMMAND_TIMEOUT_S", "8")),
        silence_hang_ms=int(os.getenv("SILENCE_HANG_MS", "800")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
