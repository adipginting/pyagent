"""Tests for the FastAPI wrapper. Skipped unless the `web` extra is installed."""

import json

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from pyagent import server  # noqa: E402
from pyagent.llm import TextChunk, ToolCall  # noqa: E402


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ("OPENROUTER_API_KEY", "KIMI_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(var, raising=False)


class FakeStream:
    """First turn calls a tool, second turn answers — then the loop stops."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, messages, tools, *, api_key, model, api_url):
        self.calls += 1
        first = self.calls == 1

        async def generate():
            if first:
                yield ToolCall(id="c1", name="read", arguments={"path": "nope.txt"})
            else:
                yield TextChunk("all done")

        return generate()


def test_health_reports_provider(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    body = TestClient(server.app).get("/api/health").json()
    assert body == {
        "status": "ok",
        "provider": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
    }


def test_chat_streams_events_in_order(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(server, "stream_chat", FakeStream())
    response = TestClient(server.app).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "hi"}]}
    )
    assert response.status_code == 200
    events = [
        json.loads(line[len("data: ") :])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [event["type"] for event in events] == [
        "tool_call",
        "tool_result",
        "text",
        "done",
    ]
    assert events[0]["name"] == "read"
    assert "nope.txt" in events[1]["output"]
    assert events[2]["text"] == "all done"


def test_chat_rejects_assistant_last_message(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    response = TestClient(server.app).post(
        "/api/chat", json={"messages": [{"role": "assistant", "content": "hi"}]}
    )
    assert response.status_code == 400
