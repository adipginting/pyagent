"""Optional OS-level sandbox for the `bash` tool, built on bubblewrap.

Path confinement (see `tools.resolve_path`) only covers `read`/`write`. A
shell can still reach absolute paths, so real isolation has to come from the
operating system. When enabled, commands run under `bwrap`: the whole
filesystem is mounted read-only, only the workspace is writable, and the
process gets its own user/PID/IPC/UTS namespaces.

It is ON by default whenever `bwrap` is installed. Opt out with
`PYAGENT_SANDBOX=0` if a command needs a writable home or `/tmp`. Disable
network with `PYAGENT_SANDBOX_NET=0`.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def available() -> bool:
    """Is bubblewrap installed?"""
    return shutil.which("bwrap") is not None


def enabled() -> bool:
    """Sandbox by default when bwrap is available; opt out with PYAGENT_SANDBOX=0."""
    if not available():
        return False
    return os.environ.get("PYAGENT_SANDBOX", "1").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


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
