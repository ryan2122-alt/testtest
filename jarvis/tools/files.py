"""File management tools, restricted to a configured allowlist of directories.

Every function here resolves its path argument(s) through
`jarvis.tools.paths.resolve_within_allowed` before touching disk. That check
raises `PathNotAllowedError`, which every handler below converts into a
normal `ToolResult(ok=False, ...)` — a refusal the LLM can relay to the
user, not a judgment call the LLM makes itself. (The registry also has a
generic catch-all, but handlers convert this specific, expected case
themselves so they behave consistently whether called via the registry or
directly.)
"""

from __future__ import annotations

import functools
import shutil
from pathlib import Path
from typing import Callable

from jarvis.tools.paths import PathNotAllowedError, resolve_within_allowed
from jarvis.tools.registry import Tool, ToolResult

MAX_LIST_ENTRIES = 200


def _guard_path_errors(handler: Callable[..., ToolResult]) -> Callable[..., ToolResult]:
    @functools.wraps(handler)
    def wrapper(*args: object, **kwargs: object) -> ToolResult:
        try:
            return handler(*args, **kwargs)
        except PathNotAllowedError as exc:
            return ToolResult(ok=False, content=str(exc))

    return wrapper


def _make_tools(allowed_dirs: tuple[Path, ...]) -> list[Tool]:
    """Build the file-tool set bound to a specific allowed-directories tuple."""

    def _resolve(raw_path: str) -> Path:
        return resolve_within_allowed(raw_path, allowed_dirs)

    def list_files(directory: str = ".") -> ToolResult:
        path = _resolve(directory)
        if not path.exists():
            return ToolResult(ok=False, content=f"'{directory}' does not exist.")
        if not path.is_dir():
            return ToolResult(ok=False, content=f"'{directory}' is not a directory.")
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
        shown = entries[:MAX_LIST_ENTRIES]
        suffix = "" if len(entries) <= MAX_LIST_ENTRIES else f" (+{len(entries) - MAX_LIST_ENTRIES} more)"
        return ToolResult(ok=True, content=", ".join(shown) + suffix if shown else "(empty)")

    def search_files(directory: str, pattern: str) -> ToolResult:
        path = _resolve(directory)
        if not path.is_dir():
            return ToolResult(ok=False, content=f"'{directory}' is not a directory.")
        matches = sorted(str(p.relative_to(path)) for p in path.rglob(pattern))
        shown = matches[:MAX_LIST_ENTRIES]
        if not shown:
            return ToolResult(ok=True, content=f"No files matching '{pattern}' in '{directory}'.")
        suffix = "" if len(matches) <= MAX_LIST_ENTRIES else f" (+{len(matches) - MAX_LIST_ENTRIES} more)"
        return ToolResult(ok=True, content=", ".join(shown) + suffix)

    def create_file(path: str, content: str = "") -> ToolResult:
        target = _resolve(path)
        if target.exists():
            return ToolResult(ok=False, content=f"'{path}' already exists.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return ToolResult(ok=True, content=f"Created '{path}'.")

    def move_file(source: str, destination: str) -> ToolResult:
        src = _resolve(source)
        dst = _resolve(destination)
        if not src.exists():
            return ToolResult(ok=False, content=f"'{source}' does not exist.")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return ToolResult(ok=True, content=f"Moved '{source}' to '{destination}'.")

    def rename_file(path: str, new_name: str) -> ToolResult:
        src = _resolve(path)
        if not src.exists():
            return ToolResult(ok=False, content=f"'{path}' does not exist.")
        if "/" in new_name or "\\" in new_name:
            return ToolResult(ok=False, content="new_name must be a plain filename, not a path.")
        dst = _resolve(str(src.parent / new_name))
        src.rename(dst)
        return ToolResult(ok=True, content=f"Renamed '{path}' to '{new_name}'.")

    def delete_file(path: str) -> ToolResult:
        target = _resolve(path)
        if not target.exists():
            return ToolResult(ok=False, content=f"'{path}' does not exist.")
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return ToolResult(ok=True, content=f"Deleted '{path}'.")

    return [
        Tool(
            spec={
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files and folders in a directory (within allowed folders).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {
                                "type": "string",
                                "description": "Directory to list, e.g. '~/Documents' or a subfolder of an allowed directory.",
                            }
                        },
                        "required": [],
                    },
                },
            },
            handler=_guard_path_errors(list_files),
        ),
        Tool(
            spec={
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Search for files matching a glob pattern within a directory (within allowed folders).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {"type": "string", "description": "Directory to search within."},
                            "pattern": {
                                "type": "string",
                                "description": "Glob pattern, e.g. '*.pdf' or '**/*.txt'.",
                            },
                        },
                        "required": ["directory", "pattern"],
                    },
                },
            },
            handler=_guard_path_errors(search_files),
        ),
        Tool(
            spec={
                "type": "function",
                "function": {
                    "name": "create_file",
                    "description": "Create a new text file with optional content (within allowed folders).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path of the file to create."},
                            "content": {"type": "string", "description": "Text content for the new file."},
                        },
                        "required": ["path"],
                    },
                },
            },
            handler=_guard_path_errors(create_file),
        ),
        Tool(
            spec={
                "type": "function",
                "function": {
                    "name": "move_file",
                    "description": "Move a file or folder to a new location (within allowed folders).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string", "description": "Current path of the file/folder."},
                            "destination": {"type": "string", "description": "Destination path."},
                        },
                        "required": ["source", "destination"],
                    },
                },
            },
            handler=_guard_path_errors(move_file),
        ),
        Tool(
            spec={
                "type": "function",
                "function": {
                    "name": "rename_file",
                    "description": "Rename a file or folder in place (within allowed folders).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path of the file/folder to rename."},
                            "new_name": {"type": "string", "description": "New filename (no slashes)."},
                        },
                        "required": ["path", "new_name"],
                    },
                },
            },
            handler=_guard_path_errors(rename_file),
        ),
        Tool(
            spec={
                "type": "function",
                "function": {
                    "name": "delete_file",
                    "description": (
                        "Permanently delete a file or folder (within allowed folders). "
                        "This executes immediately with no confirmation step — irreversible."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path of the file/folder to delete."}
                        },
                        "required": ["path"],
                    },
                },
            },
            handler=_guard_path_errors(delete_file),
        ),
    ]


def build_file_tools(allowed_dirs: tuple[Path, ...]) -> list[Tool]:
    return _make_tools(allowed_dirs)
