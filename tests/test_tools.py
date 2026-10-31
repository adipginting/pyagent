"""Tests for the three tool executors."""

import pytest

from pyagent import sandbox, tools
from pyagent.tools import bash, read, write


@pytest.fixture(autouse=True)
def confine_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "WORKSPACE", tmp_path)


async def test_read_returns_file_contents(tmp_path):
    (tmp_path / "a.txt").write_text("contents")
    assert await read(str(tmp_path / "a.txt")) == "contents"


async def test_read_relative_path_is_rooted_at_workspace(tmp_path):
    (tmp_path / "a.txt").write_text("contents")
    assert await read("a.txt") == "contents"


async def test_read_cannot_escape_workspace(tmp_path):
    (tmp_path.parent / "secret.txt").write_text("secret")
    result = await read("../secret.txt")
    assert result.startswith("Error:")
    assert "escapes the workspace" in result


async def test_write_cannot_escape_workspace(tmp_path):
    result = await write("../evil.txt", "payload")
    assert result.startswith("Error:")
    assert not (tmp_path.parent / "evil.txt").exists()


async def test_read_missing_file_is_an_error_not_a_crash(tmp_path):
    result = await read(str(tmp_path / "missing.txt"))
    assert result.startswith("Error:")


async def test_write_creates_parent_directories(tmp_path):
    target = tmp_path / "deep" / "nested" / "file.txt"
    result = await write(str(target), "payload")
    assert target.read_text() == "payload"
    assert "Wrote" in result


async def test_bash_captures_stdout_and_exit_code():
    assert await bash("echo hello") == "hello"
    failure = await bash("echo oops >&2; exit 3")
    assert "oops" in failure
    assert "exit code 3" in failure


async def test_bash_truncates_huge_output():
    output = await bash("seq 1 20000")
    assert "truncated" in output
    assert len(output) < 40_000


async def test_bash_times_out(monkeypatch):
    monkeypatch.setattr(tools, "BASH_TIMEOUT_SECONDS", 0.1)
    assert "timed out" in await bash("sleep 5")


def test_sandbox_wrap_confines_to_workspace(tmp_path):
    argv = sandbox.wrap("echo hi", tmp_path)
    assert argv[0] == "bwrap"
    assert str(tmp_path) in argv
    assert argv[-3:] == ["/bin/sh", "-c", "echo hi"]


@pytest.mark.skipif(not sandbox.available(), reason="bwrap not installed")
async def test_bash_sandbox_keeps_writes_inside_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAGENT_SANDBOX", "1")
    await bash("echo hi > inside.txt")
    assert (tmp_path / "inside.txt").read_text().strip() == "hi"

    outside = tmp_path.parent / "escaped.txt"
    result = await bash(f"echo x > {outside}")
    assert "Error: timed out" not in result
    assert not outside.exists()


def test_sandbox_enabled_by_default(monkeypatch):
    """bwrap is used automatically when installed; no env var needed."""
    monkeypatch.delenv("PYAGENT_SANDBOX", raising=False)
    assert sandbox.enabled() is sandbox.available()


def test_sandbox_can_be_disabled(monkeypatch):
    """PYAGENT_SANDBOX=0 must opt out of the sandbox."""
    monkeypatch.setenv("PYAGENT_SANDBOX", "0")
    assert sandbox.enabled() is False


def test_sandbox_masks_sensitive_paths(tmp_path, monkeypatch):
    """~/.ssh and friends must be hidden inside the sandbox."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".ssh").mkdir()
    (tmp_path / ".netrc").write_text("token")
    argv = sandbox.wrap("echo hi", tmp_path)
    joined = " ".join(argv)
    assert f"--tmpfs {tmp_path / '.ssh'}" in joined
    assert f"--ro-bind /dev/null {tmp_path / '.netrc'}" in joined


def test_sandbox_mask_env_extension(tmp_path, monkeypatch):
    """PYAGENT_SANDBOX_MASK adds extra paths."""
    extra = tmp_path / "extra-secret"
    extra.write_text("x")
    monkeypatch.setenv("PYAGENT_SANDBOX_MASK", str(extra))
    assert extra in sandbox.masked_paths()


@pytest.mark.skipif(not sandbox.available(), reason="bwrap not installed")
async def test_bash_cannot_read_masked_file(tmp_path, monkeypatch):
    """A file outside the workspace is unreadable once masked."""
    secret = tmp_path.parent / f"{tmp_path.name}-secret.txt"
    secret.write_text("topsecret")
    monkeypatch.setenv("PYAGENT_SANDBOX_MASK", str(secret))
    result = await bash(f"cat {secret}")
    assert "topsecret" not in result
