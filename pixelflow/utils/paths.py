"""Platform detection and application directory resolution.

All PixelFlow state (downloaded binaries, models, config, and temporary frame
work) lives under a single application directory so that it is easy to inspect
and to remove. The location follows OS conventions but can be overridden with
the ``PIXELFLOW_HOME`` environment variable, which keeps tests hermetic.
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

#: Environment variable that overrides the application home directory.
HOME_ENV_VAR = "PIXELFLOW_HOME"


@dataclass(frozen=True)
class PlatformInfo:
    """Normalised operating system and CPU architecture."""

    os: str  # one of: macos, linux, windows
    arch: str  # one of: arm64, x64, x86

    @property
    def label(self) -> str:
        """Human-readable label, e.g. ``macOS arm64``."""
        pretty_os = {"macos": "macOS", "linux": "Linux", "windows": "Windows"}.get(self.os, self.os)
        return f"{pretty_os} {self.arch}"

    @property
    def is_apple_silicon(self) -> bool:
        return self.os == "macos" and self.arch == "arm64"


def detect_platform() -> PlatformInfo:
    """Detect the current OS and architecture, normalised to PixelFlow names."""
    system = sys.platform
    if system.startswith("darwin"):
        os_name = "macos"
    elif system.startswith("linux"):
        os_name = "linux"
    elif system.startswith("win"):
        os_name = "windows"
    else:
        os_name = system

    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        arch = "arm64"
    elif machine in {"x86_64", "amd64"}:
        arch = "x64"
    elif machine in {"i386", "i686", "x86"}:
        arch = "x86"
    else:
        arch = machine

    return PlatformInfo(os=os_name, arch=arch)


def app_home() -> Path:
    """Return the PixelFlow application home directory.

    Honours ``PIXELFLOW_HOME`` first, then falls back to OS conventions.
    """
    override = os.environ.get(HOME_ENV_VAR)
    if override:
        return Path(override).expanduser()

    info = detect_platform()
    if info.os == "macos":
        return Path.home() / "Library" / "Application Support" / "PixelFlow"
    if info.os == "windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "PixelFlow"
    # Linux and everything else: XDG.
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "pixelflow"


@dataclass(frozen=True)
class AppPaths:
    """Resolved set of application directories."""

    home: Path

    @property
    def config_file(self) -> Path:
        return self.home / "config.json"

    @property
    def bin_dir(self) -> Path:
        """Downloaded third-party executables (ffmpeg, real-esrgan, rife)."""
        return self.home / "bin"

    @property
    def models_dir(self) -> Path:
        return self.home / "models"

    @property
    def cache_dir(self) -> Path:
        """Scratch space for extracted frames and intermediate files."""
        return self.home / "cache"

    def ensure(self) -> AppPaths:
        """Create every managed directory, returning self for chaining."""
        for directory in (self.home, self.bin_dir, self.models_dir, self.cache_dir):
            directory.mkdir(parents=True, exist_ok=True)
        return self


def app_paths() -> AppPaths:
    """Return the resolved :class:`AppPaths` for the current environment."""
    return AppPaths(home=app_home())
