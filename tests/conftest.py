"""Shared fixtures and fakes for the PixelFlow test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from pixelflow.utils.paths import AppPaths
from pixelflow.utils.process import CommandResult


@pytest.fixture
def app_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppPaths:
    """An :class:`AppPaths` rooted in a temp dir, also exported via env var."""
    home = tmp_path / "pixelflow-home"
    monkeypatch.setenv("PIXELFLOW_HOME", str(home))
    return AppPaths(home=home).ensure()


class RecordingRunner:
    """A fake subprocess runner that records calls and returns canned output."""

    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.calls: list[list[str]] = []
        self.stdout = stdout
        self.returncode = returncode

    def __call__(self, args, *, check=True, cwd=None, capture=True) -> CommandResult:
        str_args = [str(a) for a in args]
        self.calls.append(str_args)
        return CommandResult(
            args=str_args, returncode=self.returncode, stdout=self.stdout, stderr=""
        )


@pytest.fixture
def runner() -> RecordingRunner:
    return RecordingRunner()
