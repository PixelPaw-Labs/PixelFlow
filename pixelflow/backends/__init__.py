"""AI enhancement backends.

A *backend* knows how to run upscaling and/or frame interpolation on a directory
of frames. PixelFlow ships with the cross-platform NCNN Vulkan backend
(:class:`~pixelflow.backends.ncnn.NcnnVulkanBackend`) and reserves the MPS and
CoreML backends for the Apple-acceleration milestones.
"""

from __future__ import annotations

from ..config import Config
from .base import Backend, BackendCapabilityError, BackendError
from .coreml import CoreMlBackend
from .mps import MpsBackend
from .ncnn import NcnnVulkanBackend

#: Registry of backend factories keyed by their config name.
_BACKENDS: dict[str, type[Backend]] = {
    "ncnn": NcnnVulkanBackend,
    "mps": MpsBackend,
    "coreml": CoreMlBackend,
}


def available_backend_names() -> list[str]:
    """Return the registered backend names."""
    return list(_BACKENDS)


def get_backend(config: Config) -> Backend:
    """Instantiate the backend named in ``config``.

    Raises :class:`BackendError` if the configured backend is unknown.
    """
    name = config.backend
    try:
        backend_cls = _BACKENDS[name]
    except KeyError as exc:
        known = ", ".join(sorted(_BACKENDS))
        raise BackendError(f"Unknown backend {name!r}. Known backends: {known}") from exc
    return backend_cls.from_config(config)


__all__ = [
    "Backend",
    "BackendError",
    "BackendCapabilityError",
    "NcnnVulkanBackend",
    "MpsBackend",
    "CoreMlBackend",
    "get_backend",
    "available_backend_names",
]
