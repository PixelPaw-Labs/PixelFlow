"""Persistent PixelFlow configuration.

Configuration is a small JSON document stored in the application home directory.
It records the detected platform, the active backend, default model names, and
the resolved locations of the external tools so that subsequent commands do not
need to rediscover them.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .utils.paths import AppPaths, PlatformInfo, app_paths, detect_platform

#: Default Real-ESRGAN model shipped with the NCNN backend.
DEFAULT_UPSCALE_MODEL = "realesr-animevideov3"
#: Default RIFE model shipped with the NCNN backend.
DEFAULT_INTERPOLATION_MODEL = "rife-v4.6"
#: Default upscale factor used when the user does not specify one.
DEFAULT_SCALE = 2


@dataclass
class Config:
    """User- and machine-specific PixelFlow settings."""

    version: int = 1
    os: str = ""
    arch: str = ""
    backend: str = "ncnn"
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    realesrgan_path: str = "realesrgan-ncnn-vulkan"
    rife_path: str = "rife-ncnn-vulkan"
    upscale_model: str = DEFAULT_UPSCALE_MODEL
    interpolation_model: str = DEFAULT_INTERPOLATION_MODEL
    default_scale: int = DEFAULT_SCALE
    extra: dict = field(default_factory=dict)

    @classmethod
    def for_platform(cls, info: PlatformInfo | None = None) -> Config:
        """Build a default config for a platform (defaults to the current one)."""
        info = info or detect_platform()
        return cls(os=info.os, arch=info.arch)

    @classmethod
    def load(cls, paths: AppPaths | None = None) -> Config:
        """Load config from disk, falling back to platform defaults if absent."""
        paths = paths or app_paths()
        path = paths.config_file
        if not path.exists():
            return cls.for_platform()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        """Construct a Config from a dict, ignoring unknown keys gracefully."""
        known = set(cls.__dataclass_fields__)
        filtered = {k: v for k, v in data.items() if k in known}
        extra = {k: v for k, v in data.items() if k not in known}
        config = cls(**filtered)
        if extra:
            config.extra.update(extra)
        return config

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, paths: AppPaths | None = None) -> Path:
        """Persist the config to disk, creating directories as needed."""
        paths = (paths or app_paths()).ensure()
        path = paths.config_file
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path
