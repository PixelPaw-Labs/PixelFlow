"""Processing pipelines and the shared scaffolding they build on.

Each pipeline orchestrates the FFmpeg wrapper and an acceleration backend to
turn an input into an enhanced output. Pipelines receive their dependencies
explicitly (ffmpeg, backend, reporter, workspace) so they can be unit-tested
with fakes; :func:`build_dependencies` wires the real ones from config for the
CLI.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ..backends import Backend, get_backend
from ..config import Config
from ..ffmpeg import FFmpeg
from ..utils.paths import AppPaths, app_paths
from ..utils.progress import NullProgressReporter, ProgressReporter


@dataclass(frozen=True)
class PipelineResult:
    """Outcome of a completed pipeline run."""

    output: Path
    frames_processed: int = 0


@dataclass
class Dependencies:
    """The collaborators a video pipeline needs."""

    ffmpeg: FFmpeg
    backend: Backend
    config: Config
    paths: AppPaths
    reporter: ProgressReporter


def build_dependencies(
    config: Config | None = None,
    *,
    paths: AppPaths | None = None,
    reporter: ProgressReporter | None = None,
) -> Dependencies:
    """Construct real pipeline dependencies from PixelFlow config."""
    paths = paths or app_paths()
    config = config or Config.load(paths)
    ffmpeg = FFmpeg(config.ffmpeg_path, config.ffprobe_path)
    backend = get_backend(config)
    return Dependencies(
        ffmpeg=ffmpeg,
        backend=backend,
        config=config,
        paths=paths,
        reporter=reporter or NullProgressReporter(),
    )


@contextmanager
def workspace(paths: AppPaths, *, keep: bool = False) -> Iterator[Path]:
    """Yield a fresh scratch directory under the cache, cleaned up on exit."""
    paths.ensure()
    work = Path(tempfile.mkdtemp(prefix="job_", dir=paths.cache_dir))
    try:
        yield work
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)


def target_frame_count(source_frames: int, source_fps: float, target_fps: float) -> int:
    """Frames needed to retime ``source_frames`` from one fps to another."""
    if source_fps <= 0:
        raise ValueError("source fps must be positive")
    return max(1, round(source_frames * (target_fps / source_fps)))


from .enhance_video import enhance_video  # noqa: E402
from .interpolate import interpolate_video  # noqa: E402
from .upscale_image import upscale_image  # noqa: E402
from .upscale_video import upscale_video  # noqa: E402

__all__ = [
    "PipelineResult",
    "Dependencies",
    "build_dependencies",
    "workspace",
    "target_frame_count",
    "upscale_image",
    "upscale_video",
    "interpolate_video",
    "enhance_video",
]
