"""Tools: each one is a JSON schema plus an async executor function.

Executors always return a string — either the output or an "Error: ..."
message — so a failing tool becomes context for the model instead of a
crash in the agent loop.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyagent import sandbox

BASH_TIMEOUT_SECONDS = 30
MAX_OUTPUT_CHARS = 30_000

# The workspace root. None means "the current directory"; set
# PYAGENT_WORKSPACE (or assign WORKSPACE) to jail the agent elsewhere.
WORKSPACE: Path | None = None


def workspace() -> Path:
    if WORKSPACE is not None:
        return WORKSPACE.resolve()
    override = os.environ.get("PYAGENT_WORKSPACE")
    return Path(override).resolve() if override else Path.cwd().resolve()


def resolve_path(path: str) -> Path:
    """Resolve a tool path, refusing anything outside the workspace.

    Relative paths are rooted at the workspace; absolute paths are allowed
    only if they stay inside it. Symlinks are resolved first, so a link that
    points outside is rejected too.
    """
    root = workspace()
    target = Path(path)
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"path escapes the workspace ({root}): {path}")
    return target


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[..., Awaitable[str]]

    def schema(self) -> dict[str, Any]:
        """Wire-format tool definition for the chat completions API."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


async def read(path: str) -> str:
    try:
        return resolve_path(path).read_text()
    except ValueError as error:
        return f"Error: {error}"
    except FileNotFoundError:
        return f"Error: no such file: {path}"
    except IsADirectoryError:
        return f"Error: not a file: {path}"
    except UnicodeDecodeError:
        return f"Error: not a text file: {path}"


async def write(path: str, content: str) -> str:
    try:
        target = resolve_path(path)
    except ValueError as error:
        return f"Error: {error}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"Wrote {len(content)} characters to {path}"


async def bash(command: str) -> str:
    """Run a shell command from the workspace directory.

    Without a sandbox this pins the starting directory but cannot confine the
    command: a shell can still reach absolute paths. Set PYAGENT_SANDBOX=1 to
    run it under bubblewrap, where only the workspace is writable.
    """
    if sandbox.enabled():
        process = await asyncio.create_subprocess_exec(
            *sandbox.wrap(command, workspace()),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    else:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=workspace(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=BASH_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return f"Error: timed out after {BASH_TIMEOUT_SECONDS}s"

    output = stdout.decode(errors="replace") + stderr.decode(errors="replace")
    if process.returncode:
        output += f"[exit code {process.returncode}]"
    return _truncate(output.strip()) or "[no output]"


def _truncate(output: str) -> str:
    if len(output) <= MAX_OUTPUT_CHARS:
        return output
    return output[:MAX_OUTPUT_CHARS] + f"\n... [truncated: {len(output)} chars total]"


TOOLS: list[Tool] = [
    Tool(
        name="read",
        description="Read a text file in the workspace and return its contents.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file."},
            },
            "required": ["path"],
        },
        execute=read,
    ),
    Tool(
        name="write",
        description="Write content to a file in the workspace, creating parent directories as needed.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file."},
                "content": {"type": "string", "description": "Content to write."},
            },
            "required": ["path", "content"],
        },
        execute=write,
    ),
    Tool(
        name="bash",
        description=f"Run a shell command from the workspace and return its output (times out after {BASH_TIMEOUT_SECONDS}s).",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."},
            },
            "required": ["command"],
        },
        execute=bash,
    ),
]


async def execute_tool(
    name: str, arguments: dict[str, Any], tools: list[Tool] = TOOLS
) -> str:
    tool = next((t for t in tools if t.name == name), None)
    if tool is None:
        return f"Error: unknown tool: {name}"
    try:
        return await tool.execute(**arguments)
    except TypeError as error:
        return f"Error: bad arguments for {name}: {error}"
    except Exception as error:
        return f"Error: {name} failed: {error}"
