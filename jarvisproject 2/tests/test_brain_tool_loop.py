from types import SimpleNamespace

from jarvis.brain import Brain
from jarvis.prompts import API_ERROR_REPLY, TOOL_LOOP_FALLBACK_REPLY
from jarvis.tools.registry import Tool, ToolRegistry, ToolResult


def _make_response(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _make_tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=name, arguments=arguments)
    )


def _registry_with_echo_tool():
    registry = ToolRegistry()
    registry.register(
        Tool(
            spec={
                "type": "function",
                "function": {
                    "name": "echo",
                    "description": "echo",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            handler=lambda **kwargs: ToolResult(ok=True, content=f"echoed:{kwargs}"),
        )
    )
    return registry


def test_converse_returns_plain_reply_with_no_tool_calls():
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: _make_response(content="Hello there!")
            )
        )
    )
    brain = Brain("key", "model", ToolRegistry(), client=client)

    reply = brain.converse("hi")

    assert reply == "Hello there!"
    assert brain.messages[-1] == {"role": "assistant", "content": "Hello there!"}


def test_converse_executes_tool_call_then_returns_final_reply():
    responses = [
        _make_response(
            tool_calls=[_make_tool_call("call_1", "echo", '{"x": 1}')]
        ),
        _make_response(content="Done."),
    ]
    call_log = []

    def create(**kwargs):
        call_log.append(kwargs["messages"])
        return responses.pop(0)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    brain = Brain("key", "model", _registry_with_echo_tool(), client=client)

    reply = brain.converse("do the thing")

    assert reply == "Done."
    tool_messages = [m for m in brain.messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "call_1"
    assert "echoed" in tool_messages[0]["content"]
    # The second call to Groq must include the tool result in history.
    assert any(m.get("role") == "tool" for m in call_log[1])


def test_tool_loop_caps_iterations_and_returns_fallback():
    def create(**kwargs):
        return _make_response(tool_calls=[_make_tool_call("call_x", "echo", "{}")])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    brain = Brain(
        "key", "model", _registry_with_echo_tool(), client=client, max_tool_iterations=3
    )

    reply = brain.converse("loop forever")

    assert reply == TOOL_LOOP_FALLBACK_REPLY


def test_unknown_tool_call_reports_error_but_does_not_crash():
    responses = [
        _make_response(tool_calls=[_make_tool_call("call_1", "does_not_exist", "{}")]),
        _make_response(content="Sorted."),
    ]

    def create(**kwargs):
        return responses.pop(0)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    brain = Brain("key", "model", ToolRegistry(), client=client)

    reply = brain.converse("call missing tool")

    assert reply == "Sorted."
    tool_message = next(m for m in brain.messages if m.get("role") == "tool")
    assert "Unknown tool" in tool_message["content"]


def test_api_error_returns_fallback_and_pops_user_turn():
    def create(**kwargs):
        raise RuntimeError("network down")

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    brain = Brain("key", "model", ToolRegistry(), client=client)

    reply = brain.converse("hello?")

    assert reply == API_ERROR_REPLY
    assert not any(m.get("content") == "hello?" for m in brain.messages)


def test_history_is_trimmed_but_keeps_system_message():
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: _make_response(content="ok"))
        )
    )
    brain = Brain("key", "model", ToolRegistry(), client=client, max_history_messages=4)

    for i in range(10):
        brain.converse(f"message {i}")

    assert brain.messages[0]["role"] == "system"
    # Trimming happens at the *start* of each turn, so the most recent
    # untrimmed turn (user + assistant) can still be present on top of the
    # capped history.
    assert len(brain.messages) <= brain.max_history_messages + 1 + 2
