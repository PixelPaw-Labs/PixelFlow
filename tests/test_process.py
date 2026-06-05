"""Tests for the subprocess runner and executable resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pixelflow.utils.process import (
    CommandError,
    ExecutableNotFoundError,
    resolve_executable,
    run,
)


def test_run_captures_stdout() -> None:
    result = run([sys.executable, "-c", "print('hello')"])
    assert result.ok
    assert result.stdout.strip() == "hello"


def test_run_raises_on_failure() -> None:
    with pytest.raises(CommandError) as exc:
        run([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert exc.value.result.returncode == 3


def test_run_no_check_returns_result() -> None:
    result = run([sys.executable, "-c", "import sys; sys.exit(2)"], check=False)
    assert not result.ok
    assert result.returncode == 2


def test_resolve_executable_prefers_search_dir(tmp_path: Path) -> None:
    tool = tmp_path / "mytool"
    tool.write_text("#!/bin/sh\n")
    tool.chmod(0o755)
    assert resolve_executable("mytool", search=(tmp_path,)) == str(tool)


def test_resolve_executable_missing_raises() -> None:
    with pytest.raises(ExecutableNotFoundError):
        resolve_executable("definitely-not-a-real-binary-xyz")


def test_resolve_executable_absolute_path(tmp_path: Path) -> None:
    tool = tmp_path / "abs-tool"
    tool.write_text("x")
    assert resolve_executable(tool) == str(tool)
