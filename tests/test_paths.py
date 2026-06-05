"""Tests for platform detection and application directory resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from pixelflow.utils import paths as paths_mod
from pixelflow.utils.paths import AppPaths, PlatformInfo, app_home, detect_platform


def test_detect_platform_normalises_arch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths_mod.sys, "platform", "darwin")
    monkeypatch.setattr(paths_mod.platform, "machine", lambda: "arm64")
    info = detect_platform()
    assert info.os == "macos"
    assert info.arch == "arm64"
    assert info.is_apple_silicon
    assert info.label == "macOS arm64"


def test_detect_platform_maps_amd64(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths_mod.sys, "platform", "linux")
    monkeypatch.setattr(paths_mod.platform, "machine", lambda: "AMD64")
    info = detect_platform()
    assert info == PlatformInfo(os="linux", arch="x64")
    assert not info.is_apple_silicon


def test_app_home_honours_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PIXELFLOW_HOME", str(tmp_path / "custom"))
    assert app_home() == tmp_path / "custom"


def test_app_paths_ensure_creates_directories(tmp_path: Path) -> None:
    paths = AppPaths(home=tmp_path / "h").ensure()
    assert paths.bin_dir.is_dir()
    assert paths.models_dir.is_dir()
    assert paths.cache_dir.is_dir()
    assert paths.config_file == paths.home / "config.json"
