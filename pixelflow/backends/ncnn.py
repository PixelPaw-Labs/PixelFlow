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
        models_dir: str | Path | None = None,
        runner: Runner = default_run,
        resolver: Resolver = resolve_executable,
    ) -> None:
        self._realesrgan = realesrgan
        self._rife = rife
        self._paths = paths or app_paths()
        # Where the .param/.bin model files live. The NCNN tools default to a
        # "models" folder relative to the working directory, which is rarely
        # what we want, so we always point them at the managed models dir.
        self._models_dir = Path(models_dir) if models_dir is not None else self._paths.models_dir
        self._run = runner
        self._resolve = resolver

    @classmethod
    def from_config(cls, config: Config) -> NcnnVulkanBackend:
        models_dir = config.extra.get("models_dir")
        return cls(
            realesrgan=config.realesrgan_path,
            rife=config.rife_path,
            models_dir=models_dir,
        )

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

    def _realesrgan_model_args(self) -> list[str]:
        """The ``-m`` models-folder argument for Real-ESRGAN, if known."""
        return ["-m", str(self._models_dir)] if self._models_dir else []

    def _rife_model_args(self, model: str) -> list[str]:
        """The ``-m`` argument for RIFE — the model's own folder.

        RIFE's ``-m`` expects the directory containing the model's flow files,
        which lives under the managed models dir as ``<models_dir>/<model>``.
        Falls back to the bare model name when no models dir is configured.
        """
        if self._models_dir:
            return ["-m", str(self._models_dir / model)]
        return ["-m", model]

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
                *self._realesrgan_model_args(),
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
                *self._realesrgan_model_args(),
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
                *self._rife_model_args(model),
                "-n",
                str(target_frame_count),
                "-f",
                "png",
            ]
        )
        return output_dir
