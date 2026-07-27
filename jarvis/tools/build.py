"""Assembles the full ToolRegistry from all tool modules, bound to config."""

from __future__ import annotations

from jarvis.config import Config
from jarvis.tools.apps import OPEN_APP_TOOL, QUIT_APP_TOOL
from jarvis.tools.files import build_file_tools
from jarvis.tools.reminders import CREATE_REMINDER_TOOL, LIST_REMINDERS_TOOL
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system import SYSTEM_TOOLS


def build_tool_registry(config: Config) -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(OPEN_APP_TOOL)
    registry.register(QUIT_APP_TOOL)

    for tool in build_file_tools(config.allowed_dirs):
        registry.register(tool)

    registry.register(CREATE_REMINDER_TOOL)
    registry.register(LIST_REMINDERS_TOOL)

    for tool in SYSTEM_TOOLS:
        registry.register(tool)

    return registry
