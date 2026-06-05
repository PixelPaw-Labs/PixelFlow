"""Tests for the four processing pipelines and shared helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from pixelflow.backends.base import Backend
from pixelflow.config import Config
from pixelflow.ffmpeg import VideoMetadata
from pixelflow.pipelines import (
    Dependencies,
    enhance_video,
    interpolate_video,
    target_frame_count,
    upscale_image,
    upscale_video,
    workspace,
)
from pixelflow.utils.paths import AppPaths
from pixelflow.utils.progress import NullProgressReporter


class FakeBackend(Backend):
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[str] = []

    @classmethod
    def from_config(cls, config: Config) -> FakeBackend:
        return cls()

    def is_available(self) -> bool:
        return True

    @property
    def supports_upscale(self) -> bool:
        return True

    @property
    def supports_interpolation(self) -> bool:
        return True

    def upscale_image(self, source, output, *, model, scale):  # noqa: ANN001
        self.calls.append(f"upscale_image:{model}:{scale}")
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text("img")
        return Path(output)

    def upscale_frames(self, frames_dir, output_dir, *, model, scale):  # noqa: ANN001
        self.calls.append(f"upscale_frames:{model}:{scale}")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return Path(output_dir)

    def interpolate_frames(
        self, frames_dir, output_dir, *, model, target_frame_count
    ):  # noqa: ANN001
        self.calls.append(f"interpolate:{model}:{target_frame_count}")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return Path(output_dir)


class FakeFFmpeg:
    def __init__(self, meta: VideoMetadata) -> None:
        self.meta = meta
        self.calls: list[str] = []

    def probe(self, source):  # noqa: ANN001
        self.calls.append("probe")
        return self.meta

    def extract_frames(self, source, frames_dir):  # noqa: ANN001
        self.calls.append("extract")
        Path(frames_dir).mkdir(parents=True, exist_ok=True)
        return Path(frames_dir)

    def encode_frames(self, frames_dir, output, fps, *, audio_source=None, **kw):  # noqa: ANN001
        self.calls.append(f"encode:{fps}:{audio_source is not None}")
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text("video")
        return Path(output)


def _deps(app_paths: AppPaths, meta: VideoMetadata) -> tuple[Dependencies, FakeBackend, FakeFFmpeg]:
    backend = FakeBackend()
    ffmpeg = FakeFFmpeg(meta)
    config = Config(default_scale=2, upscale_model="up", interpolation_model="rife")
    deps = Dependencies(
        ffmpeg=ffmpeg,  # type: ignore[arg-type]
        backend=backend,
        config=config,
        paths=app_paths,
        reporter=NullProgressReporter(),
    )
    return deps, backend, ffmpeg


META = VideoMetadata(
    width=640, height=480, fps=30.0, duration=10.0, frame_count=300, has_audio=True
)


def test_target_frame_count() -> None:
    assert target_frame_count(300, 30.0, 60.0) == 600
    assert target_frame_count(100, 25.0, 25.0) == 100
    assert target_frame_count(1, 30.0, 1.0) == 1  # floored to at least 1


def test_target_frame_count_rejects_bad_fps() -> None:
    with pytest.raises(ValueError):
        target_frame_count(10, 0.0, 30.0)


def test_workspace_creates_and_cleans(app_paths: AppPaths) -> None:
    captured: Path | None = None
    with workspace(app_paths) as work:
        captured = work
        assert work.is_dir()
        (work / "x.txt").write_text("y")
    assert captured is not None
    assert not captured.exists()


def test_workspace_keep(app_paths: AppPaths) -> None:
    with workspace(app_paths, keep=True) as work:
        kept = work
    assert kept.exists()


def test_upscale_image_pipeline(app_paths: AppPaths) -> None:
    deps, backend, _ = _deps(app_paths, META)
    src = app_paths.home / "in.png"
    src.write_text("x")
    result = upscale_image(
        src, app_paths.home / "out.png", backend=backend, config=deps.config, scale=4
    )
    assert result.output.exists()
    assert result.frames_processed == 1
    assert backend.calls == ["upscale_image:up:4"]


def test_upscale_image_missing_input(app_paths: AppPaths) -> None:
    deps, backend, _ = _deps(app_paths, META)
    with pytest.raises(FileNotFoundError):
        upscale_image("nope.png", "out.png", backend=backend, config=deps.config)


def test_upscale_video_pipeline(app_paths: AppPaths) -> None:
    deps, backend, ffmpeg = _deps(app_paths, META)
    src = app_paths.home / "in.mp4"
    src.write_text("x")
    result = upscale_video(src, app_paths.home / "out.mp4", deps=deps, scale=2)
    assert result.frames_processed == 300
    assert "upscale_frames:up:2" in backend.calls
    # Encoded at source fps with audio.
    assert "encode:30.0:True" in ffmpeg.calls


def test_interpolate_pipeline(app_paths: AppPaths) -> None:
    deps, backend, ffmpeg = _deps(app_paths, META)
    src = app_paths.home / "in.mp4"
    src.write_text("x")
    result = interpolate_video(src, app_paths.home / "out.mp4", deps=deps, target_fps=60.0)
    assert result.frames_processed == 600
    assert "interpolate:rife:600" in backend.calls
    assert "encode:60.0:True" in ffmpeg.calls


def test_interpolate_rejects_bad_fps(app_paths: AppPaths) -> None:
    deps, _, _ = _deps(app_paths, META)
    src = app_paths.home / "in.mp4"
    src.write_text("x")
    with pytest.raises(ValueError):
        interpolate_video(src, "out.mp4", deps=deps, target_fps=0)


def test_enhance_pipeline_runs_upscale_then_interpolate(app_paths: AppPaths) -> None:
    deps, backend, ffmpeg = _deps(app_paths, META)
    src = app_paths.home / "in.mp4"
    src.write_text("x")
    result = enhance_video(src, app_paths.home / "out.mp4", deps=deps, target_fps=60.0, scale=2)
    assert result.frames_processed == 600
    # Order matters: upscale before interpolate.
    upscale_idx = backend.calls.index("upscale_frames:up:2")
    interp_idx = backend.calls.index("interpolate:rife:600")
    assert upscale_idx < interp_idx
    assert "encode:60.0:True" in ffmpeg.calls
