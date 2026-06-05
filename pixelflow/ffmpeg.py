"""FFmpeg / FFprobe wrapper.

This module is the only place that knows the exact ``ffmpeg`` and ``ffprobe``
command lines PixelFlow uses. Pipelines call high-level methods (probe, extract
frames, encode, copy audio) and never assemble argv themselves.

The subprocess runner is injected so the whole class can be exercised in tests
without a real ffmpeg binary on the machine.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from .utils.process import CommandResult
from .utils.process import run as default_run

#: Filename pattern used for extracted/processed frames (zero-padded, 1-based).
FRAME_PATTERN = "frame_%08d.png"
#: Glob equivalent of :data:`FRAME_PATTERN`.
FRAME_GLOB = "frame_*.png"

Runner = Callable[..., CommandResult]


@dataclass(frozen=True)
class VideoMetadata:
    """Subset of stream metadata PixelFlow cares about."""

    width: int
    height: int
    fps: float
    duration: float
    frame_count: int
    has_audio: bool

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


def _parse_fraction(value: str | None) -> float:
    """Parse an ffprobe rational such as ``30000/1001`` into a float."""
    if not value or value in {"0/0", "N/A"}:
        return 0.0
    try:
        return float(Fraction(value))
    except (ZeroDivisionError, ValueError):
        return 0.0


class FFmpeg:
    """High-level operations over the ffmpeg/ffprobe binaries."""

    def __init__(
        self,
        ffmpeg: str = "ffmpeg",
        ffprobe: str = "ffprobe",
        *,
        runner: Runner = default_run,
    ) -> None:
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self._run = runner

    # -- inspection --------------------------------------------------------

    def probe(self, source: str | Path) -> VideoMetadata:
        """Return :class:`VideoMetadata` for a video file via ffprobe."""
        result = self._run(
            [
                self.ffprobe,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(source),
            ]
        )
        return self._parse_probe(result.stdout)

    @staticmethod
    def _parse_probe(payload: str) -> VideoMetadata:
        data = json.loads(payload)
        streams = data.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        if video is None:
            raise ValueError("No video stream found in input")
        has_audio = any(s.get("codec_type") == "audio" for s in streams)

        fps = _parse_fraction(video.get("avg_frame_rate") or video.get("r_frame_rate"))
        fmt = data.get("format", {})
        duration = float(fmt.get("duration") or video.get("duration") or 0.0)

        frame_count = int(video.get("nb_frames") or 0)
        if frame_count == 0 and fps and duration:
            frame_count = round(fps * duration)

        return VideoMetadata(
            width=int(video.get("width") or 0),
            height=int(video.get("height") or 0),
            fps=fps,
            duration=duration,
            frame_count=frame_count,
            has_audio=has_audio,
        )

    # -- frame I/O ---------------------------------------------------------

    def extract_frames(self, source: str | Path, frames_dir: str | Path) -> Path:
        """Extract every frame of ``source`` into ``frames_dir`` as PNGs."""
        frames_dir = Path(frames_dir)
        frames_dir.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                str(source),
                "-vsync",
                "0",
                str(frames_dir / FRAME_PATTERN),
            ]
        )
        return frames_dir

    def encode_frames(
        self,
        frames_dir: str | Path,
        output: str | Path,
        fps: float,
        *,
        audio_source: str | Path | None = None,
        crf: int = 17,
        pixel_format: str = "yuv420p",
    ) -> Path:
        """Encode a directory of frames into an H.264 MP4 at ``fps``.

        When ``audio_source`` is given, its audio track is copied into the
        output (the audio is mapped from the second input, video from the
        first). The frame timeline is rebuilt from the frame sequence so this
        works for both upscaling (same fps) and interpolation (new fps).
        """
        frames_dir = Path(frames_dir)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        args: list[str] = [
            self.ffmpeg,
            "-y",
            "-framerate",
            _format_fps(fps),
            "-i",
            str(frames_dir / FRAME_PATTERN),
        ]
        if audio_source is not None:
            args += ["-i", str(audio_source)]

        args += [
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-pix_fmt",
            pixel_format,
        ]

        if audio_source is not None:
            # Map upscaled/interpolated video and the original audio; copy audio
            # untouched and drop it gracefully if the source had none.
            args += [
                "-map",
                "0:v:0",
                "-map",
                "1:a:0?",
                "-c:a",
                "copy",
                "-shortest",
            ]

        args.append(str(output))
        self._run(args)
        return output

    def list_frames(self, frames_dir: str | Path) -> list[Path]:
        """Return frame files in ``frames_dir`` sorted by their index."""
        return sorted(Path(frames_dir).glob(FRAME_GLOB))


def _format_fps(fps: float) -> str:
    """Render an fps value compactly (``30`` rather than ``30.0``)."""
    if float(fps).is_integer():
        return str(int(fps))
    return repr(float(fps))


def build_probe_command(ffprobe: str, source: str | Path) -> Sequence[str]:
    """Expose the probe argv for tests and debugging."""
    return [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(source),
    ]
