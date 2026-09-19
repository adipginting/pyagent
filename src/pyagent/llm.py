"""OpenAI-compatible streaming client: SSE in, typed events out.

Works with any chat-completions endpoint (OpenRouter, Kimi, ...).
`stream_chat` POSTs the messages and tool schemas and yields
provider-neutral events; `parse_sse` does the actual work of reducing
the wire format and is unit-tested directly.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
KIMI_API_URL = "https://api.moonshot.ai/v1/chat/completions"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "moonshotai/kimi-k2"
KIMI_DEFAULT_MODEL = "kimi-k2-0711-preview"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"
MAX_TOKENS = 8192


@dataclass(frozen=True)
class Provider:
    """One resolved provider: where to send, what key, which model."""

    api_key: str
    api_url: str
    model: str


def provider_from_env(model: str | None = None) -> Provider | None:
    """Pick a provider from the environment: OpenRouter, then Kimi, then DeepSeek."""
    if api_key := os.environ.get("OPENROUTER_API_KEY"):
        return Provider(api_key, OPENROUTER_API_URL, model or DEFAULT_MODEL)
    if api_key := os.environ.get("KIMI_API_KEY"):
        return Provider(api_key, KIMI_API_URL, model or KIMI_DEFAULT_MODEL)
    if api_key := os.environ.get("DEEPSEEK_API_KEY"):
        return Provider(api_key, DEEPSEEK_API_URL, model or DEEPSEEK_DEFAULT_MODEL)
    return None


@dataclass
class TextChunk:
    text: str


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


StreamEvent = TextChunk | ToolCall | Usage


@dataclass
class _PendingToolCall:
    """Accumulator for one tool call's fragments across SSE chunks."""

    id: str = ""
    name: str = ""
    arguments: str = ""


async def stream_chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    api_url: str = OPENROUTER_API_URL,
) -> AsyncIterator[StreamEvent]:
    """Stream one completion from an OpenAI-compatible API as typed events."""
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        # Without an explicit cap OpenRouter fills in the model's context
        # size, which some providers reject as exceeding their maximum.
        "max_tokens": MAX_TOKENS,
    }
    if tools:
        body["tools"] = tools

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            api_url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
        ) as response:
            response.raise_for_status()
            async for event in parse_sse(response.aiter_lines()):
                yield event


async def parse_sse(lines: AsyncIterator[str]) -> AsyncIterator[StreamEvent]:
    """Reduce an OpenAI-style SSE stream into typed events.

    Text arrives as chunks and streams straight through. Tool calls
    arrive as fragments (id here, name there, arguments split across
    many chunks), so they are accumulated per index and each is emitted
    as one complete ToolCall once the stream ends.
    """
    pending: dict[int, _PendingToolCall] = {}

    async for line in lines:
        line = line.strip()
        if not line.startswith("data: "):
            continue
        data = line[len("data: ") :]
        if data == "[DONE]":
            break
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue

        usage = payload.get("usage")
        if usage:
            yield Usage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            )

        choices = payload.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}

        if content := delta.get("content"):
            yield TextChunk(text=content)

        for fragment in delta.get("tool_calls") or []:
            slot = pending.setdefault(fragment.get("index", 0), _PendingToolCall())
            if fragment.get("id"):
                slot.id = fragment["id"]
            function = fragment.get("function") or {}
            if function.get("name"):
                slot.name = function["name"]
            if function.get("arguments"):
                slot.arguments += function["arguments"]

    for index in sorted(pending):
        slot = pending[index]
        try:
            arguments = json.loads(slot.arguments) if slot.arguments else {}
        except json.JSONDecodeError:
            arguments = {}
        yield ToolCall(id=slot.id, name=slot.name, arguments=arguments)
