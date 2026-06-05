"""Combined enhancement pipeline.

Input Video -> Extract Frames -> Real-ESRGAN -> RIFE -> Encode Video -> Copy
Audio -> Output Video. Upscaling runs first (on the original frames), then
interpolation runs on the upscaled frames so the synthesised frames are already
high resolution.
"""

from __future__ import annotations

from pathlib import Path

from . import Dependencies, PipelineResult, target_frame_count, workspace


def enhance_video(
    source: str | Path,
    output: str | Path,
    *,
    deps: Dependencies,
    target_fps: float,
    scale: int | None = None,
    upscale_model: str | None = None,
    interpolation_model: str | None = None,
    keep_workspace: bool = False,
) -> PipelineResult:
    """Upscale and then interpolate a video, preserving audio."""
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Input video not found: {source}")
    if target_fps <= 0:
        raise ValueError("target_fps must be positive")

    scale = scale or deps.config.default_scale
    upscale_model = upscale_model or deps.config.upscale_model
    interpolation_model = interpolation_model or deps.config.interpolation_model

    meta = deps.ffmpeg.probe(source)
    wanted = target_frame_count(meta.frame_count or 1, meta.fps or target_fps, target_fps)

    with workspace(deps.paths, keep=keep_workspace) as work:
        frames = work / "frames"
        upscaled = work / "upscaled"
        interpolated = work / "interpolated"

        with deps.reporter.task("Extracting frames", float(meta.frame_count or 1)) as task:
            deps.ffmpeg.extract_frames(source, frames)
            task.update(completed=float(meta.frame_count or 1))

        with deps.reporter.task("Upscaling frames", float(meta.frame_count or 1)) as task:
            deps.backend.upscale_frames(frames, upscaled, model=upscale_model, scale=scale)
            task.update(completed=float(meta.frame_count or 1))

        with deps.reporter.task("Interpolating frames", float(wanted)) as task:
            deps.backend.interpolate_frames(
                upscaled, interpolated, model=interpolation_model, target_frame_count=wanted
            )
            task.update(completed=float(wanted))

        with deps.reporter.task("Encoding video", 1.0) as task:
            deps.ffmpeg.encode_frames(interpolated, output, target_fps, audio_source=source)
            task.advance()

    return PipelineResult(output=Path(output), frames_processed=wanted)
