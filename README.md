# pyagent

A minimal coding agent you can read aloud: one loop, one printer, a provider
you pick from the environment. You give it a prompt, it streams text from an
LLM, calls tools (`read`, `write`, `bash`), and prints everything as it
happens.

```bash
export OPENROUTER_API_KEY="sk-or-..."
pip install -e .
pyagent "explain this repo"
```

```
▶ bash: ls -la
  → total 40
▶ read: pyproject.toml
  → [build-system]
This is pyagent, a minimal Python coding agent ...
[usage: 1033 in / 33 out]
```

## Design

![The agent loop, animated](docs/animation/agent-loop.gif)

Four core modules under `src/pyagent/`, plus a web wrapper and an optional
sandbox:

| Module | Job |
| --- | --- |
| `llm.py` | Streams an OpenAI-compatible API (OpenRouter, Kimi, or DeepSeek), parses SSE into typed events |
| `agent.py` | `AgentHarness` — the prompt → tool-call → re-prompt loop; emits events, never prints |
| `tools.py` | Three tools, each a JSON schema plus an async function |
| `cli.py` | Print mode: subscribes to the event stream and renders it |
| `server.py` | FastAPI wrapper: the same harness streamed to the browser as SSE |
| `sandbox.py` | Optional bubblewrap jail for shell commands |

The one idea: **events are the contract**. The core yields `TextDelta` /
`ToolCallStarted` / `ToolResult` / `Usage` / `Done`; any frontend — the CLI,
a test, a future TUI — just subscribes.

No TUI, no sessions, no persistence, no provider catalog. That's the point.

## Web demo (React + FastAPI)

The same agent loop behind a browser chat. `server.py` reuses `AgentHarness`
and streams its events to `web/` (a small Vite + React app).

```bash
make install                     # pip install -e ".[dev,web]" + npm install
export OPENROUTER_API_KEY="..."  # or KIMI_API_KEY / DEEPSEEK_API_KEY
make dev                         # FastAPI :8000 + Vite :5173
# open http://127.0.0.1:5173
```

`make dev` runs both dev servers. For a single process, build the UI once and
let FastAPI serve it: `make build && make api` → http://127.0.0.1:8000.

> `read`/`write` are confined to `PYAGENT_WORKSPACE` (the current directory by
> default), and shell commands can be jailed with `PYAGENT_SANDBOX=1`
> (bubblewrap). For full process isolation, run the agent in a container with
> `make sandbox`. Even so, it binds to `127.0.0.1` and is a demo, not something
> to expose.

## Isolation

Three levels, weakest to strongest:

```bash
.venv/bin/pyagent "..."                     # path-confined read/write (workspace root)
PYAGENT_SANDBOX=1 .venv/bin/pyagent "..."   # + bubblewrap jail for the shell
make sandbox PROMPT="..."                   # whole process in a container
```

`read`/`write` are confined to `PYAGENT_WORKSPACE` (the current directory by
default). See [How to run](docs/how-to-run.md) for the details.

## Docs

- [How to run](docs/how-to-run.md) — setup, API keys, commands, isolation
- [How it works](docs/how-it-works.md) — the architecture, module by module
- [Essay](docs/essay.md) — the whole thing explained in plain language
- [Talk narration](docs/narration.md) — the deck, as a presenter script

## Tests

```bash
make test        # or: .venv/bin/python -m pytest
```

23 tests: the SSE reducer, the tool executors (including path confinement),
the agent loop, the FastAPI wrapper, and the sandbox. No network or key
needed.
