"""Tests for config load/save/round-trip."""

from __future__ import annotations

from pixelflow.config import DEFAULT_SCALE, Config
from pixelflow.utils.paths import AppPaths, PlatformInfo


def test_for_platform_sets_os_and_arch() -> None:
    config = Config.for_platform(PlatformInfo(os="linux", arch="x64"))
    assert config.os == "linux"
    assert config.arch == "x64"
    assert config.default_scale == DEFAULT_SCALE


def test_save_and_load_round_trip(app_paths: AppPaths) -> None:
    config = Config.for_platform(PlatformInfo(os="macos", arch="arm64"))
    config.upscale_model = "custom-model"
    config.default_scale = 4
    path = config.save(app_paths)
    assert path.exists()

    loaded = Config.load(app_paths)
    assert loaded.upscale_model == "custom-model"
    assert loaded.default_scale == 4
    assert loaded.os == "macos"


def test_load_missing_returns_platform_defaults(app_paths: AppPaths) -> None:
    loaded = Config.load(app_paths)
    assert loaded.backend == "ncnn"
    assert loaded.os  # populated from current platform


def test_from_dict_preserves_unknown_keys_in_extra() -> None:
    config = Config.from_dict({"backend": "ncnn", "future_flag": True})
    assert config.backend == "ncnn"
    assert config.extra == {"future_flag": True}
