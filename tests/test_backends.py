"""Tests for backends: registry, NCNN command construction, and stubs."""

from __future__ import annotations

import os

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


def _ncnn(
    runner: RecordingRunner, paths: AppPaths, models_dir: str | None = None
) -> NcnnVulkanBackend:
    # A resolver that pretends every tool exists at a fixed location.
    def resolver(executable, *, search=()):  # noqa: ANN001
        return f"/fake/bin/{executable}"

    return NcnnVulkanBackend(paths=paths, models_dir=models_dir, runner=runner, resolver=resolver)


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
    backend = _ncnn(runner, app_paths, models_dir="/models")
    backend.upscale_image("in.png", app_paths.home / "out.png", model="m", scale=4)
    cmd = runner.calls[0]
    assert cmd[0] == "/fake/bin/realesrgan-ncnn-vulkan"
    assert "-s" in cmd and "4" in cmd
    assert "-n" in cmd and "m" in cmd
    # Real-ESRGAN gets the models folder via -m.
    assert cmd[cmd.index("-m") + 1] == "/models"


def test_ncnn_upscale_frames_command(runner: RecordingRunner, app_paths: AppPaths) -> None:
    backend = _ncnn(runner, app_paths, models_dir="/models")
    backend.upscale_frames(app_paths.home / "in", app_paths.home / "out", model="m", scale=2)
    cmd = runner.calls[0]
    assert "realesrgan-ncnn-vulkan" in cmd[0]
    assert "-s" in cmd and "2" in cmd
    assert cmd[cmd.index("-m") + 1] == "/models"


def test_ncnn_interpolate_command(runner: RecordingRunner, app_paths: AppPaths) -> None:
    backend = _ncnn(runner, app_paths, models_dir="/models")
    backend.interpolate_frames(
        app_paths.home / "in", app_paths.home / "out", model="rife", target_frame_count=120
    )
    cmd = runner.calls[0]
    assert "rife-ncnn-vulkan" in cmd[0]
    assert "-n" in cmd and "120" in cmd
    # RIFE gets the model's own folder under the models dir.
    assert cmd[cmd.index("-m") + 1] == "/models/rife"


def test_ncnn_rife_falls_back_to_model_name_without_models_dir(
    runner: RecordingRunner, app_paths: AppPaths
) -> None:
    backend = NcnnVulkanBackend(
        paths=app_paths,
        models_dir=None,
        runner=runner,
        resolver=lambda exe, search=(): f"/fake/{exe}",  # noqa: ANN001
    )
    # models_dir defaults to paths.models_dir, so explicitly clear it to test the fallback.
    backend._models_dir = None  # type: ignore[attr-defined]
    backend.interpolate_frames("in", "out", model="rife-v4.6", target_frame_count=10)
    cmd = runner.calls[0]
    assert cmd[cmd.index("-m") + 1] == "rife-v4.6"


def test_ncnn_from_config_reads_models_dir_override() -> None:
    config = Config(backend="ncnn")
    config.extra["models_dir"] = "/custom/models"
    backend = NcnnVulkanBackend.from_config(config)
    assert str(backend._models_dir) == "/custom/models"  # type: ignore[attr-defined]


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


def test_ncnn_ensure_executable_adds_exec_bit(tmp_path) -> None:
    # NCNN zips are built on Windows and carry no unix exec bit.
    tool = tmp_path / "realesrgan-ncnn-vulkan"
    tool.write_text("#!/bin/sh\n")
    tool.chmod(0o644)
    assert not os.access(tool, os.X_OK)

    result = NcnnVulkanBackend._ensure_executable(str(tool))

    assert result == str(tool)
    assert os.access(tool, os.X_OK)


def test_ncnn_resolve_tool_recurses_into_subfolders(
    runner: RecordingRunner, app_paths: AppPaths
) -> None:
    # `init` extracts each tool into its own subfolder; the flat search misses it.
    sub = app_paths.bin_dir / "realesrgan"
    sub.mkdir(parents=True)
    tool = sub / "realesrgan-ncnn-vulkan"
    tool.write_text("#!/bin/sh\n")
    tool.chmod(0o644)

    backend = NcnnVulkanBackend(paths=app_paths, models_dir="/models", runner=runner)
    backend.upscale_image("in.png", app_paths.home / "out.png", model="m", scale=4)

    cmd = runner.calls[0]
    assert cmd[0] == str(tool)
    # Resolution also makes the binary runnable.
    assert os.access(tool, os.X_OK)


def test_ncnn_realesrgan_prefers_adjacent_models_dir(
    runner: RecordingRunner, app_paths: AppPaths
) -> None:
    sub = app_paths.bin_dir / "realesrgan"
    sub.mkdir(parents=True)
    (sub / "realesrgan-ncnn-vulkan").write_text("bin")
    bundled_models = sub / "models"
    bundled_models.mkdir()

    backend = NcnnVulkanBackend(paths=app_paths, models_dir="/configured/models", runner=runner)
    backend.upscale_image("in.png", app_paths.home / "out.png", model="m", scale=4)

    cmd = runner.calls[0]
    # The models folder shipped beside the binary wins over the configured dir.
    assert cmd[cmd.index("-m") + 1] == str(bundled_models)


def test_ncnn_rife_prefers_bundled_model_folder(
    runner: RecordingRunner, app_paths: AppPaths
) -> None:
    sub = app_paths.bin_dir / "rife"
    sub.mkdir(parents=True)
    (sub / "rife-ncnn-vulkan").write_text("bin")
    bundled_model = sub / "rife-v4.6"
    bundled_model.mkdir()

    backend = NcnnVulkanBackend(paths=app_paths, models_dir="/configured/models", runner=runner)
    backend.interpolate_frames(
        app_paths.home / "in", app_paths.home / "out", model="rife-v4.6", target_frame_count=10
    )

    cmd = runner.calls[0]
    # RIFE's own model folder beside the binary wins over <models_dir>/<model>.
    assert cmd[cmd.index("-m") + 1] == str(bundled_model)


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
