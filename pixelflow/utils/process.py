"""Thin, testable wrapper around subprocess execution.

Every external tool invocation in PixelFlow goes through :func:`run`. Centralising
it gives us one place to handle missing executables, non-zero exit codes, and
output capture, and one seam to patch in tests so the rest of the code never has
to know whether a real binary exists.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


class ExecutableNotFoundError(FileNotFoundError):
    """Raised when a required executable cannot be located."""


@dataclass(frozen=True)
class CommandResult:
    """Outcome of a finished command."""

    args: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class CommandError(RuntimeError):
    """Raised when a command exits with a non-zero status."""

    def __init__(self, result: CommandResult) -> None:
        self.result = result
        printable = " ".join(result.args)
        super().__init__(
            f"Command failed ({result.returncode}): {printable}\n{result.stderr.strip()}"
        )


def which(executable: str) -> str | None:
    """Return the absolute path of ``executable`` on PATH, or ``None``."""
    return shutil.which(executable)


def resolve_executable(executable: str | Path, *, search: Sequence[Path] = ()) -> str:
    """Resolve an executable to an absolute path.

    Looks at the given explicit search directories first (e.g. PixelFlow's
    managed ``bin`` directory), then falls back to ``PATH``. Raises
    :class:`ExecutableNotFoundError` if it cannot be found.
    """
    candidate = Path(executable)
    if candidate.is_absolute() or candidate.parent != Path("."):
        if candidate.exists():
            return str(candidate)
    else:
        for directory in search:
            for name in (candidate.name, f"{candidate.name}.exe"):
                hit = directory / name
                if hit.exists():
                    return str(hit)
        found = which(str(executable))
        if found:
            return found
    raise ExecutableNotFoundError(f"Executable not found: {executable}")


def run(
    args: Sequence[str | Path],
    *,
    check: bool = True,
    cwd: str | Path | None = None,
    capture: bool = True,
) -> CommandResult:
    """Run a command and return a :class:`CommandResult`.

    Args:
        args: Command and arguments. The first element is the executable.
        check: When True (default), raise :class:`CommandError` on non-zero exit.
        cwd: Working directory for the child process.
        capture: When True, capture stdout/stderr; otherwise inherit the parent's.
    """
    str_args = [str(a) for a in args]
    completed = subprocess.run(
        str_args,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=capture,
        text=True,
        check=False,
    )
    result = CommandResult(
        args=str_args,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
    if check and not result.ok:
        raise CommandError(result)
    return result
