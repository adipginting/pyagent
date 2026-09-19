# How to run pyagent

## Requirements

- Python 3.14+
- One API key: OpenRouter, Kimi, **or** DeepSeek (see below)
- Optional: `bubblewrap` for the shell sandbox, Docker for full isolation

## Setup

```bash
python3.14 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Add the `web` extra (`.[dev,web]`) for the browser demo, or just run
`make install`, which installs both the Python and the JavaScript packages.

## API keys

pyagent picks its provider from the environment, OpenRouter first:

| Key | Endpoint | Default model |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | `openrouter.ai/api/v1` | `moonshotai/kimi-k2` |
| `KIMI_API_KEY` | `api.moonshot.ai/v1` | `kimi-k2-0711-preview` |
| `DEEPSEEK_API_KEY` | `api.deepseek.com/v1` | `deepseek-chat` |

```bash
# Option 1: OpenRouter — get a key at https://openrouter.ai/keys
export OPENROUTER_API_KEY="sk-or-..."

# Option 2: Kimi platform (pay-as-you-go) — create a key in the Kimi Platform console
export KIMI_API_KEY="sk-..."

# Option 3: DeepSeek — create a key at https://platform.deepseek.com/
export DEEPSEEK_API_KEY="sk-..."
```

Notes:

- Precedence is OpenRouter → Kimi → DeepSeek. If several are set, the first
  wins; `unset` the earlier keys to force a later provider.
- DeepSeek defaults to `deepseek-chat` (tool-calling). `deepseek-reasoner`
  works too, but is slower and does not support every tool-call shape — pass
  it with `-m deepseek-reasoner` if you want it.
- On OpenRouter, account data-policy settings (e.g. enforced ZDR) can silently
  remove models that lack compliant tool-calling endpoints — if you see a 404,
  try another model with `-m`.
- A **Kimi Code membership** key is different: it uses
  `https://api.kimi.com/coding/v1` and model `kimi-for-coding`. Create/manage
  keys in the Kimi Code Console (members get up to 5, shown once). Wire it in
  via `-m` and `llm.py`'s endpoint constants if you use this kind of key.

## Run

```bash
.venv/bin/pyagent "explain this repo"
# or, after `source .venv/bin/activate`:
pyagent "add a docstring to tools.py"
pyagent -m openai/gpt-4o "write a haiku into poem.txt"
```

Text streams as it arrives; tool calls print as `▶ bash: ls -la` with a
one-line result; token usage prints at the end of each turn.

## Workspace jail

The agent is confined to a workspace root — the current directory by default.
`read` and `write` resolve every path against it, and anything that resolves
outside is rejected: `../` traversal, absolute paths like `/etc/passwd`, and
symlinks that point out. Actions come back as `Error: path escapes the
workspace (...)`.

```bash
PYAGENT_WORKSPACE=/path/to/repo pyagent "explain this repo"
```

Caveat: `read`/`write` are confined, but `bash` only *starts* in the workspace
— a shell can still reach absolute paths. For real isolation, run commands
under an OS sandbox with [bubblewrap](https://github.com/containers/bubblewrap):

```bash
# whole filesystem read-only, only the workspace writable, own namespaces
PYAGENT_SANDBOX=1 pyagent "..."

# same, but no network access either
PYAGENT_SANDBOX=1 PYAGENT_SANDBOX_NET=0 pyagent "..."
```

`PYAGENT_SANDBOX=1` needs `bwrap` on `PATH` (`apt install bubblewrap`). If it
is missing, the flag is ignored and commands run unsandboxed. The sandbox
still allows *reading* system files; it prevents writes outside the workspace.

## Full isolation with Docker

`PYAGENT_SANDBOX=1` jails the shell, but the Python process still runs on your
machine. For **process isolation**, run the whole agent in a container — the
host is exposed only through the mounted workspace:

```bash
make sandbox PROMPT="explain this repo"   # build once, then run one prompt
make sandbox-web                          # web API on http://127.0.0.1:8000
```

The image installs the package and runs as a non-root user; `make sandbox`
mounts the current directory at `/workspace` and passes your provider keys
through from the environment. The server in the container serves the API only,
so pair `make sandbox-web` with `make web` on the host (Vite proxies `/api` to
`:8000`).

## Web chat (React + FastAPI)

`server.py` exposes the same `AgentHarness` over HTTP and `web/` is a small
Vite + React chat client. One `make` target installs and runs both:

```bash
make install   # pip install -e ".[dev,web]" + npm install in web/
make dev       # FastAPI on http://127.0.0.1:8000, Vite on http://127.0.0.1:5173
```

Open **http://127.0.0.1:5173** — Vite proxies `/api` to the backend. To run a
single process instead, build the UI once and let FastAPI serve it:

```bash
make build     # emits web/dist/
make api       # http://127.0.0.1:8000 serves both the API and the UI
```

The browser posts to `POST /api/chat` and reads the harness's events
(`text`, `tool_call`, `tool_result`, `usage`, `done`) as server-sent events;
`GET /api/health` reports which provider the server resolved.

> The tools include `bash`, `read`, and `write`, so anything that can reach
> the server can run commands on your machine. It binds to `127.0.0.1` and is
> meant for local demos only.

## Test

```bash
make test        # or: .venv/bin/python -m pytest
```

23 tests: the SSE reducer, the three tool executors (with path confinement),
one end-to-end agent loop against a fake provider, the FastAPI wrapper
(streaming order, health, request validation), and the sandbox. The server
tests are skipped unless the `web` extra is installed; the sandbox test is
skipped unless `bwrap` is available. No network or key needed.
