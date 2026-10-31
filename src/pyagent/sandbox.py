"""OS-level sandbox for the `bash` tool, built on bubblewrap.

Path confinement (see `tools.resolve_path`) only covers `read`/`write`. A
shell can still reach absolute paths, so real isolation has to come from the
operating system. Commands run under `bwrap`: the whole filesystem is mounted
read-only, only the workspace is writable, and the process gets its own
user/PID/IPC/UTS namespaces.

Writes are blocked everywhere outside the workspace, and a short list of
secret-bearing paths (SSH keys, cloud credentials, shell history, ...) is
masked so it cannot be *read* either — otherwise `cat ~/.ssh/id_rsa` would
still work. Add your own with `PYAGENT_SANDBOX_MASK=/path:/another/path`.

It is ON by default whenever `bwrap` is installed. Opt out with
`PYAGENT_SANDBOX=0` if a command needs a writable home or `/tmp`. Disable
network with `PYAGENT_SANDBOX_NET=0`.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# Relative to $HOME. Directories are replaced with an empty tmpfs; files are
# bound to /dev/null. Missing paths are skipped.
MASK_DIRS = (
    ".ssh",
    ".aws",
    ".gnupg",
    ".kube",
    ".docker",
    ".config/gh",
    ".config/gcloud",
)
MASK_FILES = (
    ".netrc",
    ".git-credentials",
    ".bash_history",
    ".zsh_history",
    ".npmrc",
    ".pypirc",
    ".pgpass",
)
MASK_ABSOLUTE = ("/etc/shadow",)


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


def masked_paths() -> list[Path]:
    """Paths hidden from commands: built-in secrets plus PYAGENT_SANDBOX_MASK."""
    home = Path.home()
    candidates = [home / rel for rel in MASK_DIRS]
    candidates += [home / rel for rel in MASK_FILES]
    candidates += [Path(p) for p in MASK_ABSOLUTE]
    for extra in os.environ.get("PYAGENT_SANDBOX_MASK", "").split(":"):
        if extra:
            candidates.append(Path(extra).expanduser())
    return [p for p in candidates if p.exists()]


def _mask_args() -> list[str]:
    args: list[str] = []
    for path in masked_paths():
        if path.is_dir():
            args += ["--tmpfs", str(path)]
        else:
            args += ["--ro-bind", "/dev/null", str(path)]
    return args


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
        *_mask_args(),
        "--bind", root, root,
        "--chdir", root,
        "--setenv", "HOME", root,
    ]
    if not _network_on():
        argv.append("--unshare-net")
    argv += ["/bin/sh", "-c", command]
    return argv
