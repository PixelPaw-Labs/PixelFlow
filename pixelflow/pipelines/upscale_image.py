"""Image upscaling pipeline.

Input Image -> Real-ESRGAN -> Output Image. This is the simplest pipeline: it
delegates directly to the backend with no FFmpeg involvement.
"""

from __future__ import annotations

from pathlib import Path

from ..backends import Backend
from ..config import Config
from . import PipelineResult


def upscale_image(
    source: str | Path,
    output: str | Path,
    *,
    backend: Backend,
    config: Config,
    scale: int | None = None,
    model: str | None = None,
) -> PipelineResult:
    """Upscale a single image with the configured backend."""
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Input image not found: {source}")
    scale = scale or config.default_scale
    model = model or config.upscale_model
    result = backend.upscale_image(source, output, model=model, scale=scale)
    return PipelineResult(output=result, frames_processed=1)
