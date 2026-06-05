"""Tests for the downloader: HTTP streaming, extraction, asset resolution."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from pixelflow.downloader import (
    AssetSpec,
    Downloader,
    DownloadError,
    resolve_assets,
)
from pixelflow.utils.paths import PlatformInfo


class FakeResponse:
    def __init__(self, data: bytes, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code
        self.headers = {"Content-Length": str(len(data))}

    def iter_content(self, chunk_size: int):
        for i in range(0, len(self._data), chunk_size):
            yield self._data[i : i + chunk_size]

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class FakeClient:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self._payloads = payloads
        self.requested: list[str] = []

    def get(self, url: str, *, stream: bool, timeout: float) -> FakeResponse:
        self.requested.append(url)
        return FakeResponse(self._payloads[url])


def _make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_resolve_assets_macos() -> None:
    assets = resolve_assets(PlatformInfo(os="macos", arch="arm64"))
    names = {a.name for a in assets}
    assert names == {"ffmpeg", "realesrgan", "rife"}
    realesrgan = next(a for a in assets if a.name == "realesrgan")
    assert "macos" in realesrgan.url


def test_resolve_assets_linux_uses_ubuntu_token() -> None:
    assets = resolve_assets(PlatformInfo(os="linux", arch="x64"))
    rife = next(a for a in assets if a.name == "rife")
    assert "ubuntu" in rife.url


def test_resolve_assets_unknown_platform_raises() -> None:
    with pytest.raises(DownloadError):
        resolve_assets(PlatformInfo(os="solaris", arch="sparc"))


def test_download_streams_to_file(tmp_path: Path) -> None:
    url = "https://example.com/file.bin"
    client = FakeClient({url: b"hello world"})
    downloader = Downloader(client)
    dest = downloader.download(url, tmp_path / "file.bin")
    assert dest.read_bytes() == b"hello world"
    assert client.requested == [url]


def test_extract_zip(tmp_path: Path) -> None:
    archive = tmp_path / "a.zip"
    archive.write_bytes(_make_zip({"tool": "binary", "models/x.bin": "data"}))
    downloader = Downloader(FakeClient({}))
    out = downloader.extract(archive, tmp_path / "out")
    assert (out / "tool").read_text() == "binary"
    assert (out / "models" / "x.bin").read_text() == "data"


def test_extract_unsupported_format_raises(tmp_path: Path) -> None:
    bogus = tmp_path / "not-an-archive.bin"
    bogus.write_bytes(b"random")
    with pytest.raises(DownloadError):
        Downloader(FakeClient({})).extract(bogus, tmp_path / "out")


def test_fetch_asset_downloads_and_extracts(tmp_path: Path) -> None:
    url = "https://example.com/realesrgan-macos.zip"
    client = FakeClient({url: _make_zip({"realesrgan-ncnn-vulkan": "#!/bin/sh"})})
    downloader = Downloader(client)
    asset = AssetSpec(name="realesrgan", url=url, archived=True)
    out = downloader.fetch_asset(asset, tmp_path / "dl", tmp_path / "install")
    assert (out / "realesrgan-ncnn-vulkan").exists()
