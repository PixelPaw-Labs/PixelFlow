"""NCNN Vulkan backend — the default, cross-platform acceleration target.

Wraps the standalone ``realesrgan-ncnn-vulkan`` and ``rife-ncnn-vulkan``
executables published by the upstream projects. These run on macOS, Linux, and
Windows over Vulkan and need no Python ML stack, which is why PixelFlow uses
them as the Phase 1 default.

The subprocess runner and executable-resolution seam are injectable so the
command construction can be tested without the binaries present.
"""

from __future__ import annotations

import os
import stat
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
        bin_dir = self._paths.bin_dir
        try:
            return self._ensure_executable(self._resolve(executable, search=(bin_dir,)))
        except ExecutableNotFoundError:
            # `init` extracts each tool into its own subfolder — e.g.
            # bin/realesrgan/realesrgan-ncnn-vulkan and
            # bin/rife/<versioned>/rife-ncnn-vulkan — so the flat search above
            # misses them. Fall back to a recursive search under bin_dir.
            if bin_dir.is_dir():
                for name in (executable, f"{executable}.exe"):
                    for hit in sorted(bin_dir.rglob(name)):
                        if hit.is_file():
                            return self._ensure_executable(str(hit))
            raise

    @staticmethod
    def _ensure_executable(path: str) -> str:
        """Guarantee a managed tool binary is runnable.

        The NCNN release zips are built on Windows and carry no unix
        permission bits, so the extracted ``*-ncnn-vulkan`` binaries land
        without the executable bit and fail with PermissionError. Add it when
        the file exists locally and isn't already executable; a no-op for
        PATH-resolved tools and for the fake paths used in tests.
        """
        candidate = Path(path)
        try:
            if candidate.is_file() and not os.access(candidate, os.X_OK):
                candidate.chmod(
                    candidate.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                )
        except OSError:
            pass
        return path

    def is_available(self) -> bool:
        try:
            self._resolve_tool(self._realesrgan)
            self._resolve_tool(self._rife)
        except ExecutableNotFoundError:
            return False
        return True

    def _adjacent_models_dir(self, exe: str) -> Path | None:
        """The ``models`` folder bundled beside the resolved binary, if present.

        The NCNN release archives ship the ``.param``/``.bin`` files in a
        ``models`` folder next to the executable, so prefer that over the
        configured models dir when it exists on disk.
        """
        candidate = Path(exe).parent / "models"
        return candidate if candidate.is_dir() else None

    def _realesrgan_model_args(self, exe: str) -> list[str]:
        """The ``-m`` models-folder argument for Real-ESRGAN, if known."""
        adjacent = self._adjacent_models_dir(exe)
        if adjacent is not None:
            return ["-m", str(adjacent)]
        return ["-m", str(self._models_dir)] if self._models_dir else []

    def _rife_model_args(self, exe: str, model: str) -> list[str]:
        """The ``-m`` argument for RIFE — the model's own folder.

        RIFE's ``-m`` expects the directory containing the model's flow files.
        The release archive ships those folders beside the binary
        (``<exe_dir>/<model>``); prefer that when present, then the configured
        ``<models_dir>/<model>``, and finally the bare model name.
        """
        bundled = Path(exe).parent / model
        if bundled.is_dir():
            return ["-m", str(bundled)]
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
                *self._realesrgan_model_args(exe),
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
                *self._realesrgan_model_args(exe),
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
                *self._rife_model_args(exe, model),
                "-n",
                str(target_frame_count),
                "-f",
                "png",
            ]
        )
        return output_dir
