# Changelog

All notable changes to PixelFlow are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/pixelflow/pixelflow/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/pixelflow/pixelflow/releases/tag/v0.1.0
