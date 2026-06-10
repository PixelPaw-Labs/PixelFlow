"""Download and unpack the third-party tools PixelFlow depends on.

``init`` uses this module to fetch the FFmpeg, Real-ESRGAN, and RIFE binaries
for the current platform and to extract their bundled models. The HTTP layer is
injected (any object with a ``requests``-style ``get``) so downloads can be
tested deterministically without network access.
"""

from __future__ import annotations

import os
import tarfile
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .utils.paths import PlatformInfo
from .utils.progress import NullProgressReporter, ProgressReporter

#: Streamed download chunk size in bytes.
CHUNK_SIZE = 1 << 16


class HttpResponse(Protocol):
    """Minimal subset of a ``requests`` streamed response."""

    status_code: int
    headers: dict

    def iter_content(self, chunk_size: int) -> Iterable[bytes]: ...

    def raise_for_status(self) -> None: ...

    def __enter__(self) -> HttpResponse: ...

    def __exit__(self, *exc: object) -> None: ...


class HttpClient(Protocol):
    """Minimal subset of a ``requests`` session."""

    def get(self, url: str, *, stream: bool, timeout: float) -> HttpResponse: ...


@dataclass(frozen=True)
class AssetSpec:
    """A downloadable tool: where to get it and where it lands."""

    name: str
    url: str
    archived: bool  # True if the asset is a zip/tar that must be extracted


class DownloadError(RuntimeError):
    """Raised when a download or extraction fails."""


# Release asset catalog. URLs intentionally use the upstream GitHub release
# naming patterns; they are resolved per platform by :func:`resolve_assets`.
_REALESRGAN_BASE = (
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/"
    "realesrgan-ncnn-vulkan-20220424-{platform}.zip"
)
_RIFE_BASE = (
    "https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/"
    "rife-ncnn-vulkan-20221029-{platform}.zip"
)
_FFMPEG_URLS = {
    "macos": "https://evermeet.cx/ffmpeg/getrelease/zip",
    "linux": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
    "windows": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.zip",
}
# Platform token used in the Real-ESRGAN / RIFE asset filenames.
_NCNN_PLATFORM_TOKEN = {"macos": "macos", "linux": "ubuntu", "windows": "windows"}


def resolve_assets(platform: PlatformInfo) -> list[AssetSpec]:
    """Return the asset specs required to provision the given platform."""
    token = _NCNN_PLATFORM_TOKEN.get(platform.os, platform.os)
    ffmpeg_url = _FFMPEG_URLS.get(platform.os)
    if ffmpeg_url is None:
        raise DownloadError(f"No FFmpeg download configured for platform {platform.os!r}")
    return [
        AssetSpec(name="ffmpeg", url=ffmpeg_url, archived=True),
        AssetSpec(
            name="realesrgan",
            url=_REALESRGAN_BASE.format(platform=token),
            archived=True,
        ),
        AssetSpec(name="rife", url=_RIFE_BASE.format(platform=token), archived=True),
    ]


class Downloader:
    """Streams downloads to disk and extracts archives."""

    def __init__(
        self,
        client: HttpClient,
        *,
        reporter: ProgressReporter | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._client = client
        self._reporter = reporter or NullProgressReporter()
        self._timeout = timeout

    def download(self, url: str, dest: str | Path) -> Path:
        """Download ``url`` to ``dest``, streaming with a progress bar."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._client.get(url, stream=True, timeout=self._timeout) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length", 0) or 0)
            with (
                self._reporter.task(f"Downloading {dest.name}", float(total)) as task,
                dest.open("wb") as fh,
            ):
                for chunk in response.iter_content(CHUNK_SIZE):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    task.advance(len(chunk))
        return dest

    def extract(self, archive: str | Path, dest_dir: str | Path) -> Path:
        """Extract a zip or tar archive into ``dest_dir``."""
        archive = Path(archive)
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as zf:
                _extract_zip_preserving_mode(zf, dest_dir)
        elif tarfile.is_tarfile(archive):
            with tarfile.open(archive) as tf:
                _safe_extract_tar(tf, dest_dir)
        else:
            raise DownloadError(f"Unsupported archive format: {archive.name}")
        return dest_dir

    def fetch_asset(
        self, asset: AssetSpec, download_dir: str | Path, install_dir: str | Path
    ) -> Path:
        """Download an asset and, if archived, extract it into ``install_dir``."""
        download_dir = Path(download_dir)
        install_dir = Path(install_dir)
        suffix = ".zip" if asset.url.endswith("zip") or "zip" in asset.url else ".tar.xz"
        archive_path = download_dir / f"{asset.name}{suffix}"
        self.download(asset.url, archive_path)
        if asset.archived:
            return self.extract(archive_path, install_dir / asset.name)
        target = install_dir / asset.name
        target.parent.mkdir(parents=True, exist_ok=True)
        archive_path.replace(target)
        return target


def _extract_zip_preserving_mode(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    """Extract a zip, restoring the unix permission bits.

    ``ZipFile.extractall`` discards the mode stored in each entry's
    ``external_attr`` high word, so extracted executables (e.g. the
    ``*-ncnn-vulkan`` binaries) lose their executable bit and fail to run.
    Re-apply the recorded mode after extraction whenever the archive carries
    one.
    """
    dest_root = dest_dir.resolve()
    for info in zf.infolist():
        target = (dest_dir / info.filename).resolve()
        if not str(target).startswith(str(dest_root)):
            raise DownloadError(f"Unsafe path in archive: {info.filename}")
        zf.extract(info, dest_dir)
        mode = info.external_attr >> 16
        if mode:
            os.chmod(dest_dir / info.filename, mode)


def _safe_extract_tar(tf: tarfile.TarFile, dest_dir: Path) -> None:
    """Extract a tarfile, rejecting members that escape ``dest_dir``."""
    dest_root = dest_dir.resolve()
    for member in tf.getmembers():
        target = (dest_dir / member.name).resolve()
        if not str(target).startswith(str(dest_root)):
            raise DownloadError(f"Unsafe path in archive: {member.name}")
    tf.extractall(dest_dir)
