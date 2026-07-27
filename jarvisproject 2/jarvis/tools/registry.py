"""Tool registration and dispatch for the Groq function-calling loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str


@dataclass(frozen=True)
class Tool:
    spec: dict[str, Any]  # OpenAI/Groq function-calling schema
    handler: Callable[..., ToolResult]

    @property
    def name(self) -> str:
        return self.spec["function"]["name"]


class ToolRegistry:
    """Holds the set of tools available to the assistant and dispatches calls."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def openai_tools(self) -> list[dict[str, Any]]:
        """Tool specs in the format Groq's chat.completions API expects."""
        return [tool.spec for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(ok=False, content=f"Unknown tool '{name}'")
        try:
            return tool.handler(**arguments)
        except TypeError as exc:
            return ToolResult(ok=False, content=f"Invalid arguments for '{name}': {exc}")
        except Exception as exc:  # noqa: BLE001 - tool failures must never crash the loop
            return ToolResult(ok=False, content=f"Error executing '{name}': {exc}")

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
