"""Tests for the doctor health-check report.

These tests exercise the real executable-resolution path: tool binaries are
faked as files inside the managed ``bin`` directory, so both the doctor checks
and the backend's own availability probe resolve them identically.
"""

from __future__ import annotations

from pixelflow.config import Config
from pixelflow.doctor import run_doctor
from pixelflow.utils.paths import AppPaths

NCNN_TOOLS = ("ffmpeg", "ffprobe", "realesrgan-ncnn-vulkan", "rife-ncnn-vulkan")


def _install_fake_tools(app_paths: AppPaths) -> Config:
    for tool in NCNN_TOOLS:
        path = app_paths.bin_dir / tool
        path.write_text("#!/bin/sh\n")
        path.chmod(0o755)
    return Config(
        backend="ncnn",
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
        realesrgan_path="realesrgan-ncnn-vulkan",
        rife_path="rife-ncnn-vulkan",
    )


def test_doctor_all_present(app_paths: AppPaths) -> None:
    config = _install_fake_tools(app_paths)
    report = run_doctor(config, paths=app_paths)
    by_name = {c.name: c for c in report.checks}
    assert by_name["FFmpeg"].ok
    assert by_name["Real-ESRGAN"].ok
    assert by_name["Backend"].ok
    assert by_name["Platform"].ok
    assert by_name["Temp directory"].ok
    assert report.healthy


def test_doctor_missing_tools(app_paths: AppPaths) -> None:
    # Bogus tool names that exist neither in bin/ nor on PATH.
    config = Config(
        backend="ncnn",
        ffmpeg_path="pf-missing-ffmpeg",
        ffprobe_path="pf-missing-ffprobe",
        realesrgan_path="pf-missing-realesrgan",
        rife_path="pf-missing-rife",
    )
    report = run_doctor(config, paths=app_paths)
    by_name = {c.name: c for c in report.checks}
    assert not by_name["FFmpeg"].ok
    assert not by_name["Backend"].ok
    assert not report.healthy


def test_doctor_includes_all_checks(app_paths: AppPaths) -> None:
    report = run_doctor(Config(), paths=app_paths)
    names = {c.name for c in report.checks}
    assert names == {
        "FFmpeg",
        "FFprobe",
        "Real-ESRGAN",
        "RIFE",
        "Backend",
        "Platform",
        "Temp directory",
    }
