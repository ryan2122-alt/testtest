# JARVIS

A personal, local-first voice assistant for macOS: Groq as the LLM brain,
ElevenLabs for speech, Vosk for fully offline wake-word detection and
speech recognition, and a PySide6 GUI.

> **⚠️ Risk callout — read before using tool-calling features**
> Destructive tool calls (`delete_file`, `quit_app`, `sleep_mac`,
> `restart_mac`, `shutdown_mac`) execute **immediately, with no
> confirmation prompt**, as soon as the LLM decides to call them. There is
> no "are you sure?" step. This is deliberate (see
> [Tool safety boundaries](#tool-safety-boundaries)), not a bug — but it
> means a misheard command or an unusual LLM decision could delete a file
> or restart your Mac without warning. Review that section before relying
> on this day to day.

## Prerequisites

- macOS (tested conceptually for macOS 13+; AppleScript/`osascript`-based
  tools assume a standard macOS install)
- Python 3.11+
- A [Groq API key](https://console.groq.com/keys)
- An [ElevenLabs API key](https://elevenlabs.io/app/settings/api-keys) and a voice ID

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Download a Vosk model (the small English model is enough for wake-word
spotting and works fine for commands too, at the cost of some accuracy):

```bash
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip -d models/
```

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```
GROQ_API_KEY=...
ELEVENLABS_API_KEY=...
VOICE_ID=...
```

`.env` is gitignored — never commit it.

### macOS permissions

The first time you run JARVIS, macOS will prompt for:

- **Microphone** — System Settings → Privacy & Security → Microphone → enable for your terminal app / Python.
- **Automation** — controlling the Reminders app and System Events (for reminders, app quit, lock/sleep/restart/shutdown, Do Not Disturb) triggers an automatic permission prompt on first use of each.
- **Accessibility** — required for `set_brightness` and `lock_screen`, which script System Events' UI. System Settings → Privacy & Security → Accessibility.

If you later run JARVIS from a different wrapper (e.g. a packaged `.app`
instead of bare `python`), macOS treats it as a different requester and
you'll need to re-grant these.

## Running

```bash
python -m jarvis.main            # GUI (default)
python -m jarvis.main --cli      # headless, prints state to the terminal
python -m jarvis.main --list-devices   # list audio input devices
```

Say "Jarvis", wait for the orb to change color, then speak a command. You
can also type into the GUI's text box as a fallback — it skips speech
recognition and goes straight to the brain.

## Available tools

| Tool | What it does | Example phrase |
|---|---|---|
| `open_app` / `quit_app` | Launch or quit a macOS app | "Open Safari" |
| `list_files` / `search_files` | Browse/search allowed folders | "What's in my Downloads folder?" |
| `create_file` / `move_file` / `rename_file` / `delete_file` | Manage files in allowed folders | "Delete the file called draft.txt" |
| `create_reminder` / `list_reminders` | Native Reminders.app | "Remind me to call mom tomorrow at 6pm" |
| `set_volume` / `mute` / `set_brightness` / `toggle_do_not_disturb` / `lock_screen` | Basic system controls | "Set volume to 30" |
| `sleep_mac` / `restart_mac` / `shutdown_mac` | Power actions — no confirmation | "Shut down my Mac" |

File tools only operate inside `JARVIS_ALLOWED_DIRS` (default `~/Documents,
~/Desktop, ~/Downloads`) — anything else is refused before touching disk.

## Extending with new tools

1. Add a handler function returning `ToolResult(ok, content)` and a
   `TOOL_SPEC` (or inline `Tool(spec=..., handler=...)`) in a file under
   `jarvis/tools/` (new or existing module).
2. Register it in `build_tool_registry()` in `jarvis/tools/build.py`.
3. If it touches the filesystem, route paths through
   `jarvis.tools.paths.resolve_within_allowed` like `jarvis/tools/files.py`
   does, and catch `PathNotAllowedError` in the handler (see
   `_guard_path_errors` in that file).
4. Add a unit test with `subprocess`/filesystem mocked, following the
   existing tests in `tests/test_tools_*.py`.

## Configuration reference

See `.env.example` for the full list. Key variables:

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model with tool-calling support |
| `ELEVENLABS_API_KEY` | *(required)* | ElevenLabs API key |
| `VOICE_ID` | *(required)* | ElevenLabs voice ID |
| `ELEVENLABS_MODEL_ID` | `eleven_turbo_v2_5` | ElevenLabs TTS model |
| `VOSK_MODEL_PATH` | `models/vosk-model-small-en-us-0.15` | Path to extracted Vosk model |
| `JARVIS_ALLOWED_DIRS` | `~/Documents,~/Desktop,~/Downloads` | Comma-separated file-tool allowlist |
| `COMMAND_TIMEOUT_S` | `8` | Max seconds to wait for a command after the wake word |
| `SILENCE_HANG_MS` | `800` | Trailing silence (ms) that ends a command |
| `LOG_LEVEL` | `INFO` | Log verbosity (`logs/jarvis.log`) |

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

### What's covered by automated tests (works anywhere, including CI)

- Config loading and validation
- File tool allowlist boundary, including `..` traversal and symlink-escape attempts
- App/Reminders/System AppleScript-injection escaping, argv-list `subprocess` calls
- The Groq tool-calling loop (message history, tool execution, iteration cap, error handling) — Groq client mocked
- Wake-word grammar construction and the wake/listen state logic — Vosk recognizer stubbed
- Command transcription's silence-timeout logic — Vosk recognizer stubbed, clock mocked
- ElevenLabs synthesis + `afplay` invocation — both mocked
- The `AssistantCore` state machine — all collaborators mocked
- The GUI constructs and paints without crashing — headless (`QT_QPA_PLATFORM=offscreen`)

### What you must verify yourself on your Mac

- Real wake-word recall/false-positive rate and mic quality — the
  `SILENCE_RMS_THRESHOLD` energy-based silence detector is noise-sensitive
  and will likely need tuning per-room via `SILENCE_HANG_MS`/related config.
- End-to-end latency feel (wake → spoken response).
- `afplay` actually producing audible output and ElevenLabs audio quality.
- The macOS permission prompts described above actually appearing/working.
- Reminders.app list-name matching and AppleScript date-literal correctness
  (locale-sensitive — built and tested assuming an en-US system).
- Power actions (`sleep_mac`/`restart_mac`/`shutdown_mac`) — inherently
  untestable in CI; dry-run the equivalent `osascript` commands yourself
  first if you want to confirm they do what you expect before trusting
  voice control with them.
- `sounddevice`/PortAudio device selection — if the default input device
  is wrong (e.g. a Bluetooth headset), use `--list-devices` to find the
  right index and set it in your own startup wiring.

## Tool safety boundaries

There is no confirmation dialog before destructive actions — that was an
explicit design choice. What actually protects you:

- File tools can only touch paths under `JARVIS_ALLOWED_DIRS`; this is
  enforced in code (`jarvis/tools/paths.py`), not left to the LLM's
  judgment, and rejects `..` traversal and symlink escapes.
- App names and AppleScript string arguments (reminder titles, notes) are
  validated/escaped before being interpolated into `osascript`/`open`
  commands — see `jarvis/tools/apps.py` and `jarvis/tools/reminders.py`.
- All `subprocess` calls use argument lists (`shell=False`) — no shell
  string is ever built and interpreted.
- Every tool call (name, arguments, success/failure) is logged to
  `logs/jarvis.log` for after-the-fact auditing.
- You can disable individual tools by removing their registration in
  `jarvis/tools/build.py` if you want a narrower surface — e.g. commenting
  out the power-action tools from `SYSTEM_TOOLS` if you never want voice
  control over shutdown/restart.

## Known limitations

- Energy-based (RMS) silence detection for end-of-command has no real VAD
  behind it — noisy rooms may cut you off early or the mic may never hit
  "silence" at all; tune `SILENCE_HANG_MS` and the RMS threshold in
  `jarvis/stt.py` if needed.
- The small Vosk model favors fast/low-CPU wake-word spotting over
  best-possible command transcription accuracy. A larger Vosk model can be
  swapped in for the command transcriber specifically by pointing
  `VOSK_MODEL_PATH` at it (wake-word spotting will get slower, so this is
  a manual trade-off, not automatic).
- ElevenLabs has monthly character quotas and rate limits; synthesis
  failures are caught and logged rather than crashing the assistant, but
  you'll simply not hear a spoken reply until you're back under quota.
