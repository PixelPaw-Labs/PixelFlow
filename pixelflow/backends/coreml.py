"""CoreML backend — Apple native acceleration (Phase 3).

Reserved for the milestone that runs CoreML-converted models on the Apple Neural
Engine. Registered for discoverability but not yet runnable, mirroring
:class:`~pixelflow.backends.mps.MpsBackend`.
"""

from __future__ import annotations

from ..config import Config
from .base import Backend


class CoreMlBackend(Backend):
    """Placeholder for the CoreML acceleration backend."""

    name = "coreml"

    @classmethod
    def from_config(cls, config: Config) -> CoreMlBackend:
        return cls()

    def is_available(self) -> bool:
        return False

    def _not_ready(self) -> NotImplementedError:
        return NotImplementedError(
            "The CoreML backend is planned for the Apple native-acceleration "
            "milestone and is not available yet. Use the 'ncnn' backend."
        )

    def upscale_image(self, *args, **kwargs):  # type: ignore[override]
        raise self._not_ready()

    def upscale_frames(self, *args, **kwargs):  # type: ignore[override]
        raise self._not_ready()

    def interpolate_frames(self, *args, **kwargs):  # type: ignore[override]
        raise self._not_ready()
