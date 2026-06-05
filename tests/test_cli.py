"""Tests for the Typer CLI: version, doctor, and provisioning."""

from __future__ import annotations

import io
import zipfile

from typer.testing import CliRunner

from pixelflow.cli import app, provision
from pixelflow.config import Config
from pixelflow.utils.paths import AppPaths

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "pixelflow" in result.stdout


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("init", "doctor", "upscale-image", "enhance-video"):
        assert command in result.stdout


def test_doctor_command_reports_missing(app_paths: AppPaths) -> None:
    # Real-ESRGAN/RIFE won't be installed in the test env, so doctor exits 1.
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "FFmpeg" in result.stdout


class _FakeResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self.status_code = 200
        self.headers = {"Content-Length": str(len(data))}

    def iter_content(self, chunk_size: int):
        yield self._data

    def raise_for_status(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None


class _FakeClient:
    def get(self, url: str, *, stream: bool, timeout: float):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("tool", "binary")
        return _FakeResponse(buf.getvalue())


def test_provision_writes_config_and_downloads(app_paths: AppPaths) -> None:
    config = provision(_FakeClient(), paths=app_paths)
    assert isinstance(config, Config)
    assert app_paths.config_file.exists()
    # Each asset extracted into its own directory under bin/.
    assert (app_paths.bin_dir / "ffmpeg").is_dir()
    assert (app_paths.bin_dir / "realesrgan").is_dir()
    assert (app_paths.bin_dir / "rife").is_dir()
