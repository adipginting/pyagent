"""Tests for the agent loop and for wire-format message assembly."""

import json

from pyagent.agent import (
    AgentHarness,
    Done,
    TextDelta,
    ToolCallStarted,
    ToolResult,
    assistant_message,
)
from pyagent import tools
from pyagent.llm import TextChunk, ToolCall


def test_assistant_message_text_only():
    assert assistant_message(["hello", " world"], []) == {
        "role": "assistant",
        "content": "hello world",
    }


def test_assistant_message_with_tool_calls():
    message = assistant_message(
        [], [ToolCall(id="call_1", name="bash", arguments={"command": "ls"})]
    )
    assert message == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "bash", "arguments": json.dumps({"command": "ls"})},
            }
        ],
    }


async def test_agent_loop_runs_tool_and_finishes(tmp_path, monkeypatch):
    """End to end with a fake provider: call a tool, then answer with text."""
    monkeypatch.setattr(tools, "WORKSPACE", tmp_path)
    target = tmp_path / "note.txt"
    requests = []

    async def fake_stream(messages, tools):
        requests.append([dict(message) for message in messages])
        if len(requests) == 1:
            yield ToolCall(
                id="call_1",
                name="write",
                arguments={"path": str(target), "content": "hello"},
            )
        else:
            yield TextChunk("File written.")

    harness = AgentHarness(stream=fake_stream)
    events = [event async for event in harness.run("write me a note")]

    assert [type(event) for event in events] == [
        ToolCallStarted,
        ToolResult,
        TextDelta,
        Done,
    ]
    started = events[0]
    assert started.name == "write"
    assert started.arguments == {"path": str(target), "content": "hello"}
    assert "Wrote" in events[1].output
    assert target.read_text() == "hello"

    second_request = requests[1]
    assistant = second_request[-2]
    assert assistant["role"] == "assistant"
    assert assistant["tool_calls"][0]["id"] == "call_1"
    assert second_request[-1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": events[1].output,
    }
