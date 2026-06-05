"""Backend abstraction shared by every acceleration target.

A backend exposes two optional capabilities — upscaling and frame interpolation
— operating on directories of PNG frames (and, for upscaling, single images).
Concrete backends override the capability flags and the methods they support;
unsupported operations raise :class:`BackendCapabilityError` so pipelines fail
loudly rather than silently producing wrong output.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..config import Config


class BackendError(RuntimeError):
    """Base class for backend errors."""


class BackendCapabilityError(BackendError):
    """Raised when a backend is asked to do something it does not support."""


class Backend(ABC):
    """Abstract acceleration backend."""

    #: Stable identifier used in config and the registry.
    name: str = "base"

    @classmethod
    @abstractmethod
    def from_config(cls, config: Config) -> Backend:
        """Build a backend instance from PixelFlow config."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this backend can run on the current machine."""

    @property
    def supports_upscale(self) -> bool:
        return False

    @property
    def supports_interpolation(self) -> bool:
        return False

    def upscale_image(
        self, source: str | Path, output: str | Path, *, model: str, scale: int
    ) -> Path:
        """Upscale a single image. Override in upscaling backends."""
        raise BackendCapabilityError(f"{self.name} backend does not support upscaling")

    def upscale_frames(
        self, frames_dir: str | Path, output_dir: str | Path, *, model: str, scale: int
    ) -> Path:
        """Upscale every frame in a directory. Override in upscaling backends."""
        raise BackendCapabilityError(f"{self.name} backend does not support upscaling")

    def interpolate_frames(
        self,
        frames_dir: str | Path,
        output_dir: str | Path,
        *,
        model: str,
        target_frame_count: int,
    ) -> Path:
        """Interpolate frames to reach ``target_frame_count``.

        Override in interpolation backends.
        """
        raise BackendCapabilityError(f"{self.name} backend does not support interpolation")
