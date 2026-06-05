"""Health checks for a PixelFlow installation.

``doctor`` verifies that every external dependency is present and that the
backend can run, producing a report the CLI renders as a table. The checks are
pure functions over injected collaborators so they are straightforward to test.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .backends import get_backend
from .config import Config
from .utils.paths import AppPaths, app_paths, detect_platform
from .utils.process import ExecutableNotFoundError, resolve_executable

Resolver = Callable[..., str]


@dataclass(frozen=True)
class Check:
    """Result of a single health check."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class DoctorReport:
    """Aggregate health report."""

    checks: list[Check]

    @property
    def healthy(self) -> bool:
        return all(check.ok for check in self.checks)


def _check_executable(label: str, executable: str, paths: AppPaths, resolver: Resolver) -> Check:
    try:
        location = resolver(executable, search=(paths.bin_dir,))
    except ExecutableNotFoundError:
        return Check(name=label, ok=False, detail="not found")
    return Check(name=label, ok=True, detail=location)


def _check_temp_writable(paths: AppPaths) -> Check:
    try:
        paths.ensure()
        probe = paths.cache_dir / ".doctor_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Check(name="Temp directory", ok=False, detail=str(exc))
    return Check(name="Temp directory", ok=True, detail=str(paths.cache_dir))


def run_doctor(
    config: Config | None = None,
    *,
    paths: AppPaths | None = None,
    resolver: Resolver = resolve_executable,
) -> DoctorReport:
    """Run all health checks and return a :class:`DoctorReport`."""
    paths = paths or app_paths()
    config = config or Config.load(paths)
    platform = detect_platform()

    checks = [
        _check_executable("FFmpeg", config.ffmpeg_path, paths, resolver),
        _check_executable("FFprobe", config.ffprobe_path, paths, resolver),
        _check_executable("Real-ESRGAN", config.realesrgan_path, paths, resolver),
        _check_executable("RIFE", config.rife_path, paths, resolver),
    ]

    backend = get_backend(config)
    backend_available = backend.is_available()
    checks.append(
        Check(
            name="Backend",
            ok=backend_available,
            detail=backend.name if backend_available else f"{backend.name} (unavailable)",
        )
    )
    checks.append(Check(name="Platform", ok=True, detail=platform.label))
    checks.append(_check_temp_writable(paths))

    return DoctorReport(checks=checks)
