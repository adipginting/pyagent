"""FastAPI server: the same AgentHarness the CLI uses, exposed over HTTP.

The browser talks to `POST /api/chat` and receives the harness's typed
events as server-sent events. Nothing here decides *how* the agent works —
it only translates events to JSON.

Security: the tools include `bash`, `read`, and `write`, so this server
grants whoever can reach it full local access. It binds to 127.0.0.1 by
default and is meant for a local demo, not for deployment.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from functools import partial
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pyagent.agent import AgentHarness, Done, Event, TextDelta, ToolCallStarted, ToolResult
from pyagent.llm import Provider, Usage, provider_from_env, stream_chat

NO_KEY_MESSAGE = (
    "no API key — export OPENROUTER_API_KEY, KIMI_API_KEY, or DEEPSEEK_API_KEY"
)

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"

app = FastAPI(title="pyagent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    model: str | None = None


def sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def encode(event: Event) -> dict[str, Any] | None:
    if isinstance(event, TextDelta):
        return {"type": "text", "text": event.text}
    if isinstance(event, ToolCallStarted):
        return {"type": "tool_call", "name": event.name, "arguments": event.arguments}
    if isinstance(event, ToolResult):
        return {"type": "tool_result", "name": event.name, "output": event.output}
    if isinstance(event, Usage):
        return {
            "type": "usage",
            "input_tokens": event.input_tokens,
            "output_tokens": event.output_tokens,
        }
    if isinstance(event, Done):
        return {"type": "done"}
    return None


async def event_stream(
    request: ChatRequest, provider: Provider
) -> AsyncIterator[str]:
    history = [message.model_dump() for message in request.messages[:-1]]
    prompt = request.messages[-1].content
    harness = AgentHarness(
        stream=partial(
            stream_chat,
            api_key=provider.api_key,
            model=provider.model,
            api_url=provider.api_url,
        ),
        history=history,
    )
    async for event in harness.run(prompt):
        payload = encode(event)
        if payload is not None:
            yield sse(payload)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    provider = provider_from_env()
    return {
        "status": "ok",
        "provider": provider.api_url if provider else None,
        "model": provider.model if provider else None,
    }


@app.post("/api/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    if request.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="the last message must be from the user")
    provider = provider_from_env(request.model)
    if provider is None:
        raise HTTPException(status_code=500, detail=NO_KEY_MESSAGE)
    return StreamingResponse(
        event_stream(request, provider),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")


def main() -> None:
    import uvicorn

    uvicorn.run("pyagent.server:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
