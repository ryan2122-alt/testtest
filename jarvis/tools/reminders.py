"""Create/list reminders in the native macOS Reminders app via AppleScript."""

from __future__ import annotations

import subprocess
from datetime import datetime

from jarvis.tools.registry import Tool, ToolResult

DATE_FORMAT = "%Y-%m-%d %H:%M"


def _escape_applescript(text: str) -> str:
    """Escape a string for safe interpolation into an AppleScript literal.

    Backslashes must be escaped first, then double quotes, so a title or
    note containing '"' or '\\' can't break out of the string literal and
    inject additional AppleScript commands.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _applescript_date_literal(due_date: str) -> str:
    """Convert 'YYYY-MM-DD HH:MM' into an AppleScript `date "..."` literal."""
    dt = datetime.strptime(due_date, DATE_FORMAT)
    # AppleScript's `date` parser accepts this locale-neutral-ish format on
    # an en-US system; documented as a known fragility in the README.
    return dt.strftime("%B %d, %Y %I:%M:%S %p")


def create_reminder(
    title: str, due_date: str = "", list_name: str = "Reminders", notes: str = ""
) -> ToolResult:
    safe_title = _escape_applescript(title)
    safe_notes = _escape_applescript(notes)
    safe_list = _escape_applescript(list_name)

    props = [f'name:"{safe_title}"']
    if notes:
        props.append(f'body:"{safe_notes}"')
    if due_date:
        try:
            date_literal = _applescript_date_literal(due_date)
        except ValueError:
            return ToolResult(
                ok=False,
                content=f"Invalid due_date '{due_date}'; expected format 'YYYY-MM-DD HH:MM'.",
            )
        props.append(f'due date:date "{date_literal}"')

    script = (
        f'tell application "Reminders"\n'
        f'  tell list "{safe_list}"\n'
        f"    make new reminder with properties {{{', '.join(props)}}}\n"
        f"  end tell\n"
        f"end tell"
    )
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=15
    )
    if result.returncode == 0:
        return ToolResult(ok=True, content=f"Reminder '{title}' created.")
    return ToolResult(
        ok=False, content=f"Couldn't create reminder: {result.stderr.strip() or 'unknown error'}"
    )


def list_reminders(list_name: str = "Reminders") -> ToolResult:
    safe_list = _escape_applescript(list_name)
    script = (
        f'tell application "Reminders"\n'
        f'  tell list "{safe_list}"\n'
        f"    get name of every reminder whose completed is false\n"
        f"  end tell\n"
        f"end tell"
    )
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        return ToolResult(
            ok=False, content=f"Couldn't list reminders: {result.stderr.strip() or 'unknown error'}"
        )
    names = result.stdout.strip()
    return ToolResult(ok=True, content=names if names else "No open reminders.")


CREATE_REMINDER_TOOL = Tool(
    spec={
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Create a reminder in the native macOS Reminders app.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The reminder's title."},
                    "due_date": {
                        "type": "string",
                        "description": "Optional due date/time in 'YYYY-MM-DD HH:MM' 24-hour format.",
                    },
                    "list_name": {
                        "type": "string",
                        "description": "Reminders list to add to (default 'Reminders').",
                    },
                    "notes": {"type": "string", "description": "Optional notes for the reminder."},
                },
                "required": ["title"],
            },
        },
    },
    handler=create_reminder,
)

LIST_REMINDERS_TOOL = Tool(
    spec={
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List the titles of open (incomplete) reminders in a list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "list_name": {
                        "type": "string",
                        "description": "Reminders list to read from (default 'Reminders').",
                    }
                },
                "required": [],
            },
        },
    },
    handler=list_reminders,
)
