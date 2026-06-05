"""Frame interpolation pipeline.

Input Video -> Extract Frames -> RIFE -> Encode Target FPS -> Copy Audio ->
Output Video. The output has the same resolution but a higher frame rate.
"""

from __future__ import annotations

from pathlib import Path

from . import Dependencies, PipelineResult, target_frame_count, workspace


def interpolate_video(
    source: str | Path,
    output: str | Path,
    *,
    deps: Dependencies,
    target_fps: float,
    model: str | None = None,
    keep_workspace: bool = False,
) -> PipelineResult:
    """Interpolate a video up to ``target_fps`` and copy its audio."""
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Input video not found: {source}")
    if target_fps <= 0:
        raise ValueError("target_fps must be positive")

    model = model or deps.config.interpolation_model
    meta = deps.ffmpeg.probe(source)
    wanted = target_frame_count(meta.frame_count or 1, meta.fps or target_fps, target_fps)

    with workspace(deps.paths, keep=keep_workspace) as work:
        frames = work / "frames"
        interpolated = work / "interpolated"

        with deps.reporter.task("Extracting frames", float(meta.frame_count or 1)) as task:
            deps.ffmpeg.extract_frames(source, frames)
            task.update(completed=float(meta.frame_count or 1))

        with deps.reporter.task("Interpolating frames", float(wanted)) as task:
            deps.backend.interpolate_frames(
                frames, interpolated, model=model, target_frame_count=wanted
            )
            task.update(completed=float(wanted))

        with deps.reporter.task("Encoding video", 1.0) as task:
            deps.ffmpeg.encode_frames(interpolated, output, target_fps, audio_source=source)
            task.advance()

    return PipelineResult(output=Path(output), frames_processed=wanted)
