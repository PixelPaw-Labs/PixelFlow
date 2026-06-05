"""Progress reporting helpers built on top of Rich.

Pipelines report progress through a small :class:`ProgressReporter` protocol so
that they stay decoupled from any particular UI. The default
:class:`RichProgressReporter` renders a live progress bar, while
:class:`NullProgressReporter` is a no-op used in tests and non-interactive runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)


class ProgressTask(Protocol):
    """A single unit of progress that can be advanced."""

    def advance(self, amount: float = 1.0) -> None: ...

    def update(self, *, completed: float | None = None, total: float | None = None) -> None: ...


class ProgressReporter(Protocol):
    """Creates progress tasks within a live display scope."""

    @contextmanager
    def task(self, description: str, total: float) -> Iterator[ProgressTask]: ...


class _NullTask:
    def advance(self, amount: float = 1.0) -> None:  # noqa: D102
        return None

    def update(self, *, completed: float | None = None, total: float | None = None) -> None:
        return None


class NullProgressReporter:
    """A reporter that does nothing — useful for tests and quiet mode."""

    @contextmanager
    def task(self, description: str, total: float) -> Iterator[ProgressTask]:
        yield _NullTask()


class _RichTask:
    def __init__(self, progress: Progress, task_id: int) -> None:
        self._progress = progress
        self._task_id = task_id

    def advance(self, amount: float = 1.0) -> None:
        self._progress.advance(self._task_id, amount)

    def update(self, *, completed: float | None = None, total: float | None = None) -> None:
        kwargs: dict[str, float] = {}
        if completed is not None:
            kwargs["completed"] = completed
        if total is not None:
            kwargs["total"] = total
        if kwargs:
            self._progress.update(self._task_id, **kwargs)


class RichProgressReporter:
    """Renders progress with a Rich live progress bar."""

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()

    @contextmanager
    def task(self, description: str, total: float) -> Iterator[ProgressTask]:
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self._console,
            transient=False,
        )
        with progress:
            task_id = progress.add_task(description, total=total)
            yield _RichTask(progress, task_id)
