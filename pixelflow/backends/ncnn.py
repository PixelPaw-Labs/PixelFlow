"""NCNN Vulkan backend — the default, cross-platform acceleration target.

Wraps the standalone ``realesrgan-ncnn-vulkan`` and ``rife-ncnn-vulkan``
executables published by the upstream projects. These run on macOS, Linux, and
Windows over Vulkan and need no Python ML stack, which is why PixelFlow uses
them as the Phase 1 default.

The subprocess runner and executable-resolution seam are injectable so the
command construction can be tested without the binaries present.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..config import Config
from ..utils.paths import AppPaths, app_paths
from ..utils.process import (
    CommandResult,
    ExecutableNotFoundError,
    resolve_executable,
)
from ..utils.process import (
    run as default_run,
)
from .base import Backend, BackendError

Runner = Callable[..., CommandResult]
Resolver = Callable[..., str]


class NcnnVulkanBackend(Backend):
    """Real-ESRGAN + RIFE via their NCNN Vulkan command-line tools."""

    name = "ncnn"

    def __init__(
        self,
        *,
        realesrgan: str = "realesrgan-ncnn-vulkan",
        rife: str = "rife-ncnn-vulkan",
        paths: AppPaths | None = None,
        runner: Runner = default_run,
        resolver: Resolver = resolve_executable,
    ) -> None:
        self._realesrgan = realesrgan
        self._rife = rife
        self._paths = paths or app_paths()
        self._run = runner
        self._resolve = resolver

    @classmethod
    def from_config(cls, config: Config) -> NcnnVulkanBackend:
        return cls(realesrgan=config.realesrgan_path, rife=config.rife_path)

    @property
    def supports_upscale(self) -> bool:
        return True

    @property
    def supports_interpolation(self) -> bool:
        return True

    # -- discovery ---------------------------------------------------------

    def _resolve_tool(self, executable: str) -> str:
        return self._resolve(executable, search=(self._paths.bin_dir,))

    def is_available(self) -> bool:
        try:
            self._resolve_tool(self._realesrgan)
            self._resolve_tool(self._rife)
        except ExecutableNotFoundError:
            return False
        return True

    # -- upscaling ---------------------------------------------------------

    def upscale_image(
        self, source: str | Path, output: str | Path, *, model: str, scale: int
    ) -> Path:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        exe = self._resolve_tool(self._realesrgan)
        self._run(
            [
                exe,
                "-i",
                str(source),
                "-o",
                str(output),
                "-n",
                model,
                "-s",
                str(scale),
                "-f",
                "png",
            ]
        )
        return output

    def upscale_frames(
        self, frames_dir: str | Path, output_dir: str | Path, *, model: str, scale: int
    ) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        exe = self._resolve_tool(self._realesrgan)
        # Real-ESRGAN NCNN processes a whole directory when -i/-o are folders.
        self._run(
            [
                exe,
                "-i",
                str(frames_dir),
                "-o",
                str(output_dir),
                "-n",
                model,
                "-s",
                str(scale),
                "-f",
                "png",
            ]
        )
        return output_dir

    # -- interpolation -----------------------------------------------------

    def interpolate_frames(
        self,
        frames_dir: str | Path,
        output_dir: str | Path,
        *,
        model: str,
        target_frame_count: int,
    ) -> Path:
        if target_frame_count <= 0:
            raise BackendError("target_frame_count must be positive")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        exe = self._resolve_tool(self._rife)
        # RIFE NCNN's -n requests an explicit output frame count, letting it hit
        # an arbitrary target fps rather than only doubling.
        self._run(
            [
                exe,
                "-i",
                str(frames_dir),
                "-o",
                str(output_dir),
                "-m",
                model,
                "-n",
                str(target_frame_count),
                "-f",
                "png",
            ]
        )
        return output_dir
