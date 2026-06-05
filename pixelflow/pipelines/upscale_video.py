"""Video upscaling pipeline.

Input Video -> Extract Frames -> Real-ESRGAN -> Encode Video -> Copy Audio ->
Output Video. The output keeps the source frame rate; only spatial resolution
changes.
"""

from __future__ import annotations

from pathlib import Path

from . import Dependencies, PipelineResult, workspace


def upscale_video(
    source: str | Path,
    output: str | Path,
    *,
    deps: Dependencies,
    scale: int | None = None,
    model: str | None = None,
    keep_workspace: bool = False,
) -> PipelineResult:
    """Upscale every frame of a video, preserving fps and audio."""
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Input video not found: {source}")

    scale = scale or deps.config.default_scale
    model = model or deps.config.upscale_model

    meta = deps.ffmpeg.probe(source)
    with workspace(deps.paths, keep=keep_workspace) as work:
        frames = work / "frames"
        upscaled = work / "upscaled"

        with deps.reporter.task("Extracting frames", float(meta.frame_count or 1)) as task:
            deps.ffmpeg.extract_frames(source, frames)
            task.update(completed=float(meta.frame_count or 1))

        with deps.reporter.task("Upscaling frames", float(meta.frame_count or 1)) as task:
            deps.backend.upscale_frames(frames, upscaled, model=model, scale=scale)
            task.update(completed=float(meta.frame_count or 1))

        with deps.reporter.task("Encoding video", 1.0) as task:
            deps.ffmpeg.encode_frames(upscaled, output, meta.fps, audio_source=source)
            task.advance()

    return PipelineResult(output=Path(output), frames_processed=meta.frame_count)
