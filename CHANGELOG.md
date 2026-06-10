# Changelog

All notable changes to PixelFlow are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-06-11

### Fixed

- Preserve the unix executable bit when extracting tool archives, and add it
  back on resolution, so the `*-ncnn-vulkan` binaries from the Windows-built
  NCNN release zips are runnable instead of failing with `PermissionError`.
- Discover backend binaries recursively under the managed `bin` directory:
  `init` extracts each tool into its own subfolder (e.g.
  `bin/realesrgan/realesrgan-ncnn-vulkan`), which the previous flat search
  missed.
- Prefer the `models`/model folder that ships beside the resolved binary for
  the Real-ESRGAN and RIFE `-m` argument, falling back to the configured
  models directory.

### Added

- Auto-provision the backend on first use: enhancement commands run the
  one-time setup (download + extract) when the backend isn't ready yet, so no
  caller needs to pre-run `init` or hand-write config.
- `uv` install and run instructions in the README (`uv tool install`, `uvx`).

## [0.1.0] - 2026-06-06

Initial release.

### Added

- Typer-based CLI with six commands: `init`, `doctor`, `upscale-image`,
  `upscale-video`, `interpolate`, and `enhance-video`, plus `--version`.
- Cross-platform NCNN Vulkan backend wrapping the Real-ESRGAN and RIFE
  command-line tools (macOS, Linux, Windows). The backend passes the managed
  models directory to the tools via `-m` (overridable via the config `extra`
  map), and was verified end-to-end upscaling 720p footage to 4K UHD.
- FFmpeg/FFprobe wrapper: metadata probing, frame extraction, H.264 encoding,
  and audio passthrough.
- Four processing pipelines: image upscale, video upscale, frame interpolation,
  and combined enhance (upscale + interpolate).
- `init` provisioning that detects the platform and downloads + extracts FFmpeg
  and the AI backends, with a streamed progress bar.
- `doctor` health checks for FFmpeg, FFprobe, Real-ESRGAN, RIFE, the GPU
  backend, platform, and a writable temp directory.
- Persistent JSON configuration under an OS-appropriate application directory
  (overridable via `PIXELFLOW_HOME`).
- Registered (not-yet-runnable) MPS and CoreML backend stubs for the planned
  Apple-acceleration milestones.
- Test suite (pytest), linting (ruff), and formatting (black) configuration;
  ~89% coverage at release.
- Specification document under `docs/SPEC.md`.

[Unreleased]: https://github.com/PixelPaw-Labs/PixelFlow/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/PixelPaw-Labs/PixelFlow/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/PixelPaw-Labs/PixelFlow/releases/tag/v0.1.0
