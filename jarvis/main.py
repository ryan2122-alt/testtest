"""Entry point: wires config -> tools -> brain -> voice pipeline -> TTS -> GUI/CLI."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from pathlib import Path
from typing import Any

from jarvis.audio_input import MicStream, list_devices
from jarvis.brain import Brain
from jarvis.config import Config, ConfigError, load_config
from jarvis.core import AssistantCore, AssistantEvent
from jarvis.logging_setup import setup_logging
from jarvis.stt import CommandTranscriber
from jarvis.tools.build import build_tool_registry
from jarvis.tts import ElevenLabsTTS
from jarvis.wake import WakeWordDetector

logger = logging.getLogger("jarvis.main")


def _print_event(event: AssistantEvent) -> None:
    label = event.kind.name.replace("_", " ").title()
    print(f"[{label}] {event.payload}" if event.payload else f"[{label}]")


def _load_vosk_model(model_path: Path) -> Any:
    import vosk

    if not model_path.exists():
        raise SystemExit(
            f"Vosk model not found at '{model_path}'. Download one from "
            "https://alphacephei.com/vosk/models, extract it, and set "
            "VOSK_MODEL_PATH in .env to point at the extracted folder."
        )
    vosk.SetLogLevel(-1)
    return vosk.Model(str(model_path))


def build_core(config: Config) -> AssistantCore:
    registry = build_tool_registry(config)
    brain = Brain(config.groq_api_key, config.groq_model, registry)
    tts = ElevenLabsTTS(config.elevenlabs_api_key, config.voice_id, config.elevenlabs_model_id)

    model = _load_vosk_model(config.vosk_model_path)
    mic_stream = MicStream()
    wake_detector = WakeWordDetector(model)
    transcriber = CommandTranscriber(
        model,
        silence_hang_ms=config.silence_hang_ms,
        command_timeout_s=config.command_timeout_s,
    )

    return AssistantCore(config, wake_detector, transcriber, brain, tts, mic_stream)


def run_cli(config: Config) -> None:
    core = build_core(config)
    core.on_event = _print_event
    stop_flag = threading.Event()
    print('JARVIS is listening. Say "Jarvis" to begin. Press Ctrl+C to quit.')
    try:
        core.run_forever(stop_flag)
    except KeyboardInterrupt:
        stop_flag.set()
        print("\nStopping.")


def run_gui(config: Config) -> None:
    from PySide6.QtWidgets import QApplication

    from jarvis.gui.main_window import MainWindow

    core = build_core(config)
    app = QApplication(sys.argv)
    window = MainWindow(core)
    window.show()
    app.aboutToQuit.connect(window.worker.stop)
    sys.exit(app.exec())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JARVIS — local voice assistant")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--cli", action="store_true", help="Run headless in the terminal")
    mode.add_argument("--gui", action="store_true", help="Run the graphical interface (default)")
    parser.add_argument(
        "--list-devices", action="store_true", help="List audio input devices and exit"
    )
    parser.add_argument("--log-level", default=None, help="Override LOG_LEVEL from .env")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if args.list_devices:
        print(list_devices())
        return

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    setup_logging(config.log_dir, args.log_level or config.log_level)

    if args.cli:
        run_cli(config)
    else:
        run_gui(config)


if __name__ == "__main__":
    main()
