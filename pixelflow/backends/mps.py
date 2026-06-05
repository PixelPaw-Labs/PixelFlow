"""PyTorch MPS backend — Apple Silicon optimisation (Phase 2).

Reserved for the milestone that runs Real-ESRGAN / RIFE through PyTorch with
Metal Performance Shaders acceleration. The class is registered so ``doctor``
and the backend registry can report it, but it is not yet runnable: it advertises
itself as unavailable and its operations raise a clear NotImplementedError.
"""

from __future__ import annotations

from ..config import Config
from .base import Backend


class MpsBackend(Backend):
    """Placeholder for the PyTorch MPS acceleration backend."""

    name = "mps"

    @classmethod
    def from_config(cls, config: Config) -> MpsBackend:
        return cls()

    def is_available(self) -> bool:
        # Becomes a real availability probe (torch.backends.mps.is_available)
        # when the Phase 2 milestone lands.
        return False

    def _not_ready(self) -> NotImplementedError:
        return NotImplementedError(
            "The MPS backend is planned for the Apple-optimisation milestone "
            "and is not available yet. Use the 'ncnn' backend."
        )

    def upscale_image(self, *args, **kwargs):  # type: ignore[override]
        raise self._not_ready()

    def upscale_frames(self, *args, **kwargs):  # type: ignore[override]
        raise self._not_ready()

    def interpolate_frames(self, *args, **kwargs):  # type: ignore[override]
        raise self._not_ready()
