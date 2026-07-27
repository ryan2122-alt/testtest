"""Groq-backed conversational brain with function/tool-calling."""

from __future__ import annotations

import json
import logging
from typing import Any

from groq import Groq

from jarvis.prompts import API_ERROR_REPLY, SYSTEM_PROMPT, TOOL_LOOP_FALLBACK_REPLY
from jarvis.tools.registry import ToolRegistry

logger = logging.getLogger("jarvis.brain")

MAX_TOOL_ITERATIONS = 6
MAX_HISTORY_MESSAGES = 40  # excluding the system message


class BrainError(RuntimeError):
    """Raised when the Groq API itself fails (network, auth, rate limit)."""


def _tool_call_to_message_dict(tool_call: Any) -> dict[str, Any]:
    if isinstance(tool_call, dict):
        return tool_call
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.function.name,
            "arguments": tool_call.function.arguments,
        },
    }


class Brain:
    """Owns conversation history and runs the Groq tool-calling loop."""

    def __init__(
        self,
        api_key: str,
        model: str,
        tool_registry: ToolRegistry,
        client: Any = None,
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
        max_history_messages: int = MAX_HISTORY_MESSAGES,
    ) -> None:
        self.model = model
        self.tool_registry = tool_registry
        self.client = client or Groq(api_key=api_key)
        self.max_tool_iterations = max_tool_iterations
        self.max_history_messages = max_history_messages
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _trim_history(self) -> None:
        if len(self.messages) > self.max_history_messages + 1:
            self.messages = [self.messages[0]] + self.messages[-self.max_history_messages :]

    def converse(self, user_text: str) -> str:
        """Send a user turn through the tool-calling loop, return final reply text."""
        self._trim_history()
        self.messages.append({"role": "user", "content": user_text})
        try:
            return self._run_tool_loop()
        except BrainError as exc:
            logger.error("Groq API error: %s", exc)
            # Drop the unanswered user turn so a failed call doesn't pollute
            # history with a question that never got a reply.
            if self.messages and self.messages[-1]["role"] == "user":
                self.messages.pop()
            return API_ERROR_REPLY

    def _run_tool_loop(self) -> str:
        for _ in range(self.max_tool_iterations):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=self.tool_registry.openai_tools(),
                    tool_choice="auto",
                )
            except Exception as exc:  # noqa: BLE001 - network/SDK errors -> BrainError
                raise BrainError(str(exc)) from exc

            choice = response.choices[0].message
            tool_calls = getattr(choice, "tool_calls", None)

            if not tool_calls:
                content = choice.content or ""
                self.messages.append({"role": "assistant", "content": content})
                return content

            self.messages.append(
                {
                    "role": "assistant",
                    "content": choice.content,
                    "tool_calls": [_tool_call_to_message_dict(tc) for tc in tool_calls],
                }
            )

            for tool_call in tool_calls:
                call_dict = _tool_call_to_message_dict(tool_call)
                name = call_dict["function"]["name"]
                raw_args = call_dict["function"]["arguments"] or "{}"
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    result_content = f"Error: malformed arguments for '{name}'"
                else:
                    logger.info("tool_call name=%s args=%s", name, args)
                    result = self.tool_registry.execute(name, args)
                    logger.info("tool_result name=%s ok=%s", name, result.ok)
                    result_content = result.content

                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_dict["id"],
                        "name": name,
                        "content": result_content,
                    }
                )

        logger.warning("Tool loop did not converge after %d iterations", self.max_tool_iterations)
        self.messages.append({"role": "assistant", "content": TOOL_LOOP_FALLBACK_REPLY})
        return TOOL_LOOP_FALLBACK_REPLY
