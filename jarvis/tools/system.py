"""System controls: volume, brightness, lock screen, and power actions.

Power actions (sleep/restart/shutdown) execute immediately with no
confirmation prompt, per explicit product decision — see README's Safety
section. Every command here is a fixed, argument-free (or numerically
bounded) AppleScript/shell invocation with no free-text interpolation, so
there is no injection surface even without a confirmation gate.
"""

from __future__ import annotations

import subprocess

from jarvis.tools.registry import Tool, ToolResult


def _run_osascript(script: str, description: str) -> ToolResult:
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        return ToolResult(ok=True, content=description)
    return ToolResult(
        ok=False, content=f"Failed: {result.stderr.strip() or 'unknown error'}"
    )


def set_volume(level: int) -> ToolResult:
    level = max(0, min(100, int(level)))
    return _run_osascript(
        f"set volume output volume {level}", f"Volume set to {level}%."
    )


def mute(muted: bool = True) -> ToolResult:
    return _run_osascript(
        f"set volume output muted {'true' if muted else 'false'}",
        "Muted." if muted else "Unmuted.",
    )


def set_brightness(level: int) -> ToolResult:
    # `osascript` has no native brightness verb; drive it via key events
    # (F1/F2) is unreliable across Macs, so we use System Events' brightness
    # property, which requires Accessibility permission (documented).
    level = max(0, min(100, int(level))) / 100
    script = f'tell application "System Events" to set brightness of first display to {level}'
    return _run_osascript(script, f"Brightness set to {int(level * 100)}%.")


def toggle_do_not_disturb(enabled: bool = True) -> ToolResult:
    # Control Center's DND toggle isn't reliably scriptable via AppleScript
    # across macOS versions, so this writes the underlying preference key
    # directly via `defaults` instead.
    state = "true" if enabled else "false"
    result = subprocess.run(
        [
            "defaults",
            "-currentHost",
            "write",
            "~/Library/Preferences/ByHost/com.apple.notificationcenterui",
            "doNotDisturb",
            "-boolean",
            state,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode == 0:
        return ToolResult(
            ok=True, content=f"Do Not Disturb {'enabled' if enabled else 'disabled'}."
        )
    return ToolResult(
        ok=False, content=f"Couldn't toggle Do Not Disturb: {result.stderr.strip()}"
    )


def lock_screen() -> ToolResult:
    script = 'tell application "System Events" to keystroke "q" using {control down, command down}'
    return _run_osascript(script, "Screen locked.")


def sleep_mac() -> ToolResult:
    return _run_osascript('tell application "System Events" to sleep', "Going to sleep.")


def restart_mac() -> ToolResult:
    return _run_osascript('tell application "System Events" to restart', "Restarting.")


def shutdown_mac() -> ToolResult:
    return _run_osascript('tell application "System Events" to shut down', "Shutting down.")


SYSTEM_TOOLS = [
    Tool(
        spec={
            "type": "function",
            "function": {
                "name": "set_volume",
                "description": "Set the system output volume (0-100).",
                "parameters": {
                    "type": "object",
                    "properties": {"level": {"type": "integer", "description": "Volume 0-100."}},
                    "required": ["level"],
                },
            },
        },
        handler=set_volume,
    ),
    Tool(
        spec={
            "type": "function",
            "function": {
                "name": "mute",
                "description": "Mute or unmute system audio.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "muted": {"type": "boolean", "description": "true to mute, false to unmute."}
                    },
                    "required": [],
                },
            },
        },
        handler=mute,
    ),
    Tool(
        spec={
            "type": "function",
            "function": {
                "name": "set_brightness",
                "description": "Set the main display brightness (0-100). Requires Accessibility permission.",
                "parameters": {
                    "type": "object",
                    "properties": {"level": {"type": "integer", "description": "Brightness 0-100."}},
                    "required": ["level"],
                },
            },
        },
        handler=set_brightness,
    ),
    Tool(
        spec={
            "type": "function",
            "function": {
                "name": "toggle_do_not_disturb",
                "description": "Enable or disable Do Not Disturb.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean", "description": "true to enable, false to disable."}
                    },
                    "required": [],
                },
            },
        },
        handler=toggle_do_not_disturb,
    ),
    Tool(
        spec={
            "type": "function",
            "function": {
                "name": "lock_screen",
                "description": "Lock the screen immediately.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        handler=lock_screen,
    ),
    Tool(
        spec={
            "type": "function",
            "function": {
                "name": "sleep_mac",
                "description": "Put the Mac to sleep immediately. No confirmation step.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        handler=sleep_mac,
    ),
    Tool(
        spec={
            "type": "function",
            "function": {
                "name": "restart_mac",
                "description": "Restart the Mac immediately. No confirmation step — unsaved work may be lost.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        handler=restart_mac,
    ),
    Tool(
        spec={
            "type": "function",
            "function": {
                "name": "shutdown_mac",
                "description": "Shut down the Mac immediately. No confirmation step — unsaved work may be lost.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        handler=shutdown_mac,
    ),
]
