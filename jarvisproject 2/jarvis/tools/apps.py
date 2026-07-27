"""Open/quit macOS applications by name."""

from __future__ import annotations

import re
import subprocess

from jarvis.tools.registry import Tool, ToolResult

# Application names are plain, human-readable strings (letters, digits,
# spaces, and a small set of punctuation seen in real app names like
# "Notes", "1Password", "Bear – Notes"). Anything else is refused before it
# ever reaches `open`/`osascript`, so a prompt-injected app name can't be
# used to smuggle shell/AppleScript metacharacters.
_APP_NAME_RE = re.compile(r"^[A-Za-z0-9À-ÿ .,'&()\-]{1,80}$")


def _validate_app_name(name: str) -> str:
    name = name.strip()
    if not _APP_NAME_RE.match(name):
        raise ValueError(f"App name '{name}' contains disallowed characters")
    return name


def open_app(app_name: str) -> ToolResult:
    try:
        name = _validate_app_name(app_name)
    except ValueError as exc:
        return ToolResult(ok=False, content=str(exc))
    result = subprocess.run(
        ["open", "-a", name], capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        return ToolResult(ok=True, content=f"Opened {name}.")
    return ToolResult(
        ok=False, content=f"Couldn't open {name}: {result.stderr.strip() or 'not found'}"
    )


def quit_app(app_name: str) -> ToolResult:
    try:
        name = _validate_app_name(app_name)
    except ValueError as exc:
        return ToolResult(ok=False, content=str(exc))
    script = f'tell application "{name}" to quit'
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        return ToolResult(ok=True, content=f"Quit {name}.")
    return ToolResult(
        ok=False, content=f"Couldn't quit {name}: {result.stderr.strip() or 'unknown error'}"
    )


OPEN_APP_TOOL = Tool(
    spec={
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open/launch a macOS application by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "The application's name, e.g. 'Safari', 'Notes', 'Spotify'.",
                    }
                },
                "required": ["app_name"],
            },
        },
    },
    handler=open_app,
)

QUIT_APP_TOOL = Tool(
    spec={
        "type": "function",
        "function": {
            "name": "quit_app",
            "description": "Quit a running macOS application by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "The application's name, e.g. 'Safari', 'Notes', 'Spotify'.",
                    }
                },
                "required": ["app_name"],
            },
        },
    },
    handler=quit_app,
)
