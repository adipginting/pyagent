"""Optional OS-level sandbox for the `bash` tool, built on bubblewrap.

Path confinement (see `tools.resolve_path`) only covers `read`/`write`. A
shell can still reach absolute paths, so real isolation has to come from the
operating system. When enabled, commands run under `bwrap`: the whole
filesystem is mounted read-only, only the workspace is writable, and the
process gets its own user/PID/IPC/UTS namespaces.

This is opt-in because it can break commands that expect a writable home or
`/tmp`. Enable it with `PYAGENT_SANDBOX=1`; disable network with
`PYAGENT_SANDBOX_NET=0`.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

TRUTHY = {"1", "true", "yes", "on"}


def available() -> bool:
    """Is bubblewrap installed?"""
    return shutil.which("bwrap") is not None


def enabled() -> bool:
    """Should commands be sandboxed? Opt-in via PYAGENT_SANDBOX."""
    return os.environ.get("PYAGENT_SANDBOX", "").lower() in TRUTHY and available()


def _network_on() -> bool:
    return os.environ.get("PYAGENT_SANDBOX_NET", "1").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def wrap(command: str, workspace: Path) -> list[str]:
    """Build the bwrap argv for running `command` from `workspace`."""
    root = str(workspace)
    argv = [
        "bwrap",
        "--die-with-parent",
        "--unshare-user",
        "--unshare-uts",
        "--unshare-ipc",
        "--unshare-pid",
        "--ro-bind", "/", "/",
        "--dev-bind", "/dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
        "--bind", root, root,
        "--chdir", root,
        "--setenv", "HOME", root,
    ]
    if not _network_on():
        argv.append("--unshare-net")
    argv += ["/bin/sh", "-c", command]
    return argv
