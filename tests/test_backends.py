"""Tests for backends: registry, NCNN command construction, and stubs."""

from __future__ import annotations

import pytest

from pixelflow.backends import (
    BackendCapabilityError,
    BackendError,
    CoreMlBackend,
    MpsBackend,
    NcnnVulkanBackend,
    available_backend_names,
    get_backend,
)
from pixelflow.backends.base import Backend
from pixelflow.config import Config
from pixelflow.utils.paths import AppPaths
from pixelflow.utils.process import ExecutableNotFoundError
from tests.conftest import RecordingRunner


def _ncnn(runner: RecordingRunner, paths: AppPaths) -> NcnnVulkanBackend:
    # A resolver that pretends every tool exists at a fixed location.
    def resolver(executable, *, search=()):  # noqa: ANN001
        return f"/fake/bin/{executable}"

    return NcnnVulkanBackend(paths=paths, runner=runner, resolver=resolver)


def test_registry_lists_backends() -> None:
    assert set(available_backend_names()) == {"ncnn", "mps", "coreml"}


def test_get_backend_returns_configured() -> None:
    backend = get_backend(Config(backend="ncnn"))
    assert isinstance(backend, NcnnVulkanBackend)


def test_get_backend_unknown_raises() -> None:
    with pytest.raises(BackendError, match="Unknown backend"):
        get_backend(Config(backend="nope"))


def test_ncnn_capabilities() -> None:
    backend = NcnnVulkanBackend()
    assert backend.supports_upscale
    assert backend.supports_interpolation


def test_ncnn_upscale_image_command(runner: RecordingRunner, app_paths: AppPaths) -> None:
    backend = _ncnn(runner, app_paths)
    backend.upscale_image("in.png", app_paths.home / "out.png", model="m", scale=4)
    cmd = runner.calls[0]
    assert cmd[0] == "/fake/bin/realesrgan-ncnn-vulkan"
    assert "-s" in cmd and "4" in cmd
    assert "-n" in cmd and "m" in cmd


def test_ncnn_upscale_frames_command(runner: RecordingRunner, app_paths: AppPaths) -> None:
    backend = _ncnn(runner, app_paths)
    backend.upscale_frames(app_paths.home / "in", app_paths.home / "out", model="m", scale=2)
    cmd = runner.calls[0]
    assert "realesrgan-ncnn-vulkan" in cmd[0]
    assert "-s" in cmd and "2" in cmd


def test_ncnn_interpolate_command(runner: RecordingRunner, app_paths: AppPaths) -> None:
    backend = _ncnn(runner, app_paths)
    backend.interpolate_frames(
        app_paths.home / "in", app_paths.home / "out", model="rife", target_frame_count=120
    )
    cmd = runner.calls[0]
    assert "rife-ncnn-vulkan" in cmd[0]
    assert "-n" in cmd and "120" in cmd


def test_ncnn_interpolate_rejects_nonpositive(runner: RecordingRunner, app_paths: AppPaths) -> None:
    backend = _ncnn(runner, app_paths)
    with pytest.raises(BackendError):
        backend.interpolate_frames("in", "out", model="rife", target_frame_count=0)


def test_ncnn_is_available_false_when_missing(app_paths: AppPaths) -> None:
    def resolver(executable, *, search=()):  # noqa: ANN001
        raise ExecutableNotFoundError(executable)

    backend = NcnnVulkanBackend(paths=app_paths, resolver=resolver)
    assert backend.is_available() is False


def test_ncnn_is_available_true_when_present(app_paths: AppPaths) -> None:
    backend = _ncnn(RecordingRunner(), app_paths)
    assert backend.is_available() is True


@pytest.mark.parametrize("backend_cls", [MpsBackend, CoreMlBackend])
def test_stub_backends_unavailable(backend_cls: type[Backend]) -> None:
    backend = backend_cls.from_config(Config())
    assert backend.is_available() is False
    with pytest.raises(NotImplementedError):
        backend.upscale_image("in", "out", model="m", scale=2)
    with pytest.raises(NotImplementedError):
        backend.interpolate_frames("in", "out", model="m", target_frame_count=10)


def test_base_backend_unsupported_capability() -> None:
    backend = NcnnVulkanBackend()

    # base default raises for an unsupported op — exercise via a bare subclass
    class Bare(Backend):
        name = "bare"

        @classmethod
        def from_config(cls, config: Config) -> Bare:
            return cls()

        def is_available(self) -> bool:
            return True

    bare = Bare()
    with pytest.raises(BackendCapabilityError):
        bare.upscale_image("a", "b", model="m", scale=2)
    with pytest.raises(BackendCapabilityError):
        bare.interpolate_frames("a", "b", model="m", target_frame_count=2)
    assert backend.name == "ncnn"
