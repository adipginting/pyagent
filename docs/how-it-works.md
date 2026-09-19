# How pyagent works

pyagent is a minimal coding agent: you give it a prompt, it talks to an LLM,
calls tools, and prints everything as it happens. The core is four small
modules under `src/pyagent/`, designed so each can be read aloud; a web
wrapper and an optional sandbox sit around it.

## The one idea: events are the contract

Nothing in the core prints, renders, or writes files for display. The agent
loop **yields typed events**, and whatever runs the agent — the CLI, a test,
a future TUI — subscribes and decides what to show.

```
cli.py  ──subscribes──▶  agent.py  ──streams from──▶  llm.py
(prints)                 (the loop, no I/O)            (provider, no printing)
                                │
                                └──calls──▶ tools.py (read / write / bash)
```

## The loop (`agent.py`)

`AgentHarness.run(prompt)` is the whole brain:

1. Append the user prompt to the message list (plain dicts, OpenAI wire format).
2. Stream one completion from the LLM, yielding `TextDelta` events as text arrives.
3. If the model asked for tool calls: yield `ToolCallStarted`, execute the tool,
   yield `ToolResult`, append the result to the messages, and go to step 2.
4. If the model asked for nothing: yield `Done` and stop.

A run is bounded by `MAX_ITERATIONS` (25), so a model that keeps calling
tools forever gets stopped instead of looping into the sunset.

## The provider (`llm.py`)

One endpoint per run, over the OpenAI-compatible chat completions API:
OpenRouter when `OPENROUTER_API_KEY` is set, Kimi direct
(`api.moonshot.ai`) when only `KIMI_API_KEY` is, or DeepSeek direct
(`api.deepseek.com`) when only `DEEPSEEK_API_KEY` is. `stream_chat` POSTs
the messages and tool schemas with `stream: true` and parses the
server-sent-events response.

The subtle part: tool calls don't arrive whole. The id, the name, and the
arguments stream in as fragments spread across many chunks, so `parse_sse`
accumulates them per call and emits one complete `ToolCall` each when the
stream ends. Text, by contrast, flows straight through as `TextChunk`s —
that's what makes the output feel live.

## The tools (`tools.py`)

A tool is just a JSON schema plus an async function that returns a string:

- `read(path)` — return a file's contents
- `write(path, content)` — write a file, creating parent directories
- `bash(command)` — run a shell command (30s timeout, output truncated at 30k chars)

Executors never raise: a failure comes back as an `"Error: ..."` string,
which becomes context for the model — it can see what went wrong and try
something else, instead of crashing the loop.

`read` and `write` are also confined to a **workspace root**: the current
directory by default, or whatever `PYAGENT_WORKSPACE` points at. Every path is
resolved against it first, so `../`, absolute paths, and symlinks that point
outside all come back as `Error: path escapes the workspace (...)`.

## The CLI (`cli.py`)

`pyagent "explain this repo"` — print mode only. It subscribes to the event
stream and renders it to the terminal: text streams token by token, tool
calls print as `▶ bash: ls -la`, results as a one-line summary, and token
usage at the end. It needs one thing: a key in the environment
(`OPENROUTER_API_KEY`, `KIMI_API_KEY` for Kimi direct, or
`DEEPSEEK_API_KEY` for DeepSeek direct). Model defaults to the provider's
default, overridable with `-m`.

## The web server (`server.py` + `web/`)

The browser demo reuses everything above. `server.py` wraps `AgentHarness` in
FastAPI: `POST /api/chat` takes the conversation and returns the harness's
typed events as server-sent events; `web/` (Vite + React) renders them. The
server only translates events to JSON — the loop, tools, and provider
selection are shared with the CLI. Because the tools include `bash`, it binds
to `127.0.0.1` and is a local demo, not a deployment.

## Confinement and isolation

Path confinement covers the file tools, but a shell can still reach absolute
paths, so there are two stronger layers around the harness:

- **Shell sandbox (`sandbox.py`).** With `PYAGENT_SANDBOX=1`, `bash` runs under
  [bubblewrap](https://github.com/containers/bubblewrap): the filesystem is
  read-only, only the workspace is writable, `/tmp` is fresh, and the command
  gets its own user/PID/IPC/UTS namespaces. `PYAGENT_SANDBOX_NET=0` also cuts
  the network. Without `bwrap`, the flag is ignored.
- **Container (`Dockerfile`).** `make sandbox` runs the whole process in a
  container with only the workspace mounted — the Python harness included.

Details are in [How to run](how-to-run.md).

## The tests

Deliberately thin, aimed where bugs hide:

- `test_llm.py` — the SSE reducer (fragments in, complete tool calls out)
- `test_tools.py` — the three executors, their error paths, workspace
  confinement, and (when `bwrap` is present) the shell sandbox
- `test_agent.py` — one end-to-end loop with a fake provider: model asks
  for a tool, tool runs, model answers, `Done`
- `test_server.py` — the FastAPI wrapper: event order, health, validation
  (skipped when the `web` extra isn't installed)

The fake provider is the trick worth stealing: the harness takes its stream
function as a parameter, so tests drive the entire loop without any network.

## What pyagent doesn't do

No TUI, no sessions, no persistence, no provider catalog. That's not a
roadmap — it's the point. One loop, one printer, plus a thin HTTP wrapper for
the web demo and an optional sandbox.
