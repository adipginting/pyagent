"""AgentHarness: owns the message list and the agent loop.

Events are the contract — the harness never prints, it yields typed
events and the caller (CLI, tests, anything) decides what to show.
Messages are plain dicts in OpenAI wire format.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from pyagent.llm import StreamEvent, TextChunk, ToolCall, Usage
from pyagent.tools import TOOLS, Tool, execute_tool

MAX_ITERATIONS = 25


@dataclass
class TextDelta:
    text: str


@dataclass
class ToolCallStarted:
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    name: str
    output: str


@dataclass
class Done:
    pass


Event = TextDelta | ToolCallStarted | ToolResult | Usage | Done

StreamFn = Callable[
    [list[dict[str, Any]], list[dict[str, Any]]], AsyncIterator[StreamEvent]
]


def assistant_message(text_parts: list[str], tool_calls: list[ToolCall]) -> dict[str, Any]:
    """Assemble one streamed response into an OpenAI wire-format message."""
    message: dict[str, Any] = {"role": "assistant", "content": "".join(text_parts) or None}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in tool_calls
        ]
    return message


class AgentHarness:
    """The prompt → stream → tool-call → re-prompt loop."""

    def __init__(
        self,
        stream: StreamFn,
        tools: list[Tool] = TOOLS,
        history: list[dict[str, Any]] | None = None,
    ) -> None:
        self._stream = stream
        self._tools = tools
        self.messages: list[dict[str, Any]] = list(history) if history else []

    async def run(self, prompt: str) -> AsyncIterator[Event]:
        """Drive the loop until the model stops calling tools."""
        self.messages.append({"role": "user", "content": prompt})

        for _ in range(MAX_ITERATIONS):
            text_parts: list[str] = []
            tool_calls: list[ToolCall] = []

            schemas = [tool.schema() for tool in self._tools]
            async for event in self._stream(self.messages, schemas):
                if isinstance(event, TextChunk):
                    text_parts.append(event.text)
                    yield TextDelta(event.text)
                elif isinstance(event, ToolCall):
                    tool_calls.append(event)
                elif isinstance(event, Usage):
                    yield event

            self.messages.append(assistant_message(text_parts, tool_calls))

            if not tool_calls:
                yield Done()
                return

            for call in tool_calls:
                yield ToolCallStarted(call.name, call.arguments)
                output = await execute_tool(call.name, call.arguments, self._tools)
                yield ToolResult(call.name, output)
                self.messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": output}
                )

        yield TextDelta("[stopped: hit the iteration limit]")
        yield Done()
