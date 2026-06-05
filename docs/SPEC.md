# PixelFlow Specification

PixelFlow is a cross-platform AI video enhancement CLI. It upscales images and
videos with Real-ESRGAN, interpolates video frame rates with RIFE, and combines
both in a single "enhance" pass — all orchestrated around FFmpeg.

> **Tagline:** Upscale. Interpolate. Enhance.

This document describes the implemented architecture and behaviour. It is the
source of truth for how the pieces fit together; the implementation plan
(`PixelFlow-Implementation-Plan.md`) describes the longer-term roadmap.

---

## 1. Commands

| Command | Purpose |
| --- | --- |
| `pixelflow init` | Detect the platform, download FFmpeg + AI backends, write config, run health checks. |
| `pixelflow doctor` | Report whether FFmpeg, FFprobe, Real-ESRGAN, RIFE, the GPU backend, and the temp dir are ready. |
| `pixelflow upscale-image SRC -o OUT [--scale N] [--model M]` | Upscale a single image. |
| `pixelflow upscale-video SRC -o OUT [--scale N] [--model M]` | Upscale a video, preserving fps and audio. |
| `pixelflow interpolate SRC -o OUT --fps F [--model M]` | Raise a video's frame rate. |
| `pixelflow enhance-video SRC -o OUT --fps F [--scale N]` | Upscale then interpolate in one pass. |
| `pixelflow --version` | Print the version. |

Exit codes: commands return `0` on success and a non-zero code on failure
(`doctor` returns `1` when any check fails; `init` returns `1` if provisioning
fails).

---

## 2. Architecture

```text
CLI (Typer)
  │
  ├─ Config            persisted JSON settings + platform info
  ├─ Doctor            health checks over the resolved tools/backend
  ├─ Downloader        fetch + extract FFmpeg / Real-ESRGAN / RIFE
  │
  ├─ FFmpeg wrapper    probe · extract frames · encode · copy audio
  ├─ Backend           upscale + interpolate (NCNN today; MPS/CoreML later)
  │
  └─ Pipelines
       ├─ upscale_image      Real-ESRGAN only
       ├─ upscale_video      extract → upscale → encode (+audio)
       ├─ interpolate        extract → RIFE → encode @ target fps (+audio)
       └─ enhance_video      extract → upscale → RIFE → encode (+audio)
```

### Layering rules

- **Pipelines** orchestrate; they never build argv or touch subprocess directly.
- **FFmpeg wrapper** is the only owner of ffmpeg/ffprobe command lines.
- **Backends** are the only owners of Real-ESRGAN / RIFE command lines.
- **`utils/process`** is the single subprocess seam (resolution, capture,
  error handling). Every external invocation goes through it.
- Every external boundary (subprocess runner, HTTP client, executable resolver,
  progress reporter) is **injectable**, so the logic is testable without the
  real binaries or network.

---

## 3. Configuration

Stored as JSON at the application home directory:

- macOS: `~/Library/Application Support/PixelFlow/config.json`
- Linux: `$XDG_DATA_HOME/pixelflow/` (or `~/.local/share/pixelflow/`)
- Windows: `%LOCALAPPDATA%\PixelFlow\`
- Override everything with the `PIXELFLOW_HOME` environment variable.

Managed subdirectories: `bin/` (downloaded executables), `models/`, `cache/`
(scratch space for frame extraction; each job gets a temp subdir that is removed
on completion).

Fields: `version`, `os`, `arch`, `backend`, tool paths (`ffmpeg_path`,
`ffprobe_path`, `realesrgan_path`, `rife_path`), default model names
(`upscale_model`, `interpolation_model`), `default_scale`, and an `extra` bag
that preserves forward-compatible unknown keys.

---

## 4. Pipelines

### Image upscaling
`Input → Real-ESRGAN → Output`. Delegates straight to the backend.

### Video upscaling
`Input → extract frames → Real-ESRGAN (per frame) → encode → copy audio`.
Output keeps the **source frame rate**; only resolution changes.

### Frame interpolation
`Input → extract frames → RIFE → encode @ target fps → copy audio`.
The required output frame count is computed as
`round(source_frames × target_fps / source_fps)` (floored to at least 1).

### Enhance video
`Input → extract → Real-ESRGAN → RIFE → encode → copy audio`. Upscaling runs
**first** so interpolation synthesises already-high-resolution frames.

Audio handling: when encoding, the original input is supplied as a second FFmpeg
input and its audio stream is copied (`-map 1:a:0?`), gracefully degrading to no
audio if the source had none (`-shortest` keeps streams aligned).

---

## 5. Backends

| Backend | Status | Notes |
| --- | --- | --- |
| `ncnn` | **Default** | Real-ESRGAN + RIFE NCNN Vulkan binaries; macOS/Linux/Windows. |
| `mps` | Planned (Phase 2) | PyTorch Metal acceleration on Apple Silicon. |
| `coreml` | Planned (Phase 3) | CoreML-converted models on the Neural Engine. |

A backend advertises two optional capabilities — `supports_upscale` and
`supports_interpolation` — and raises `BackendCapabilityError` if asked to do
something it does not support. The `mps`/`coreml` stubs are registered for
discoverability but report themselves unavailable and raise `NotImplementedError`
if invoked.

### NCNN model resolution

The NCNN tools load their weights from a models folder rather than from the
executable name alone, so PixelFlow always points them at the managed models
directory:

- **Real-ESRGAN** receives `-n <model>` (e.g. `realesr-animevideov3`) plus
  `-m <models_dir>`; the tool then loads `<models_dir>/<model>-x<scale>.{param,bin}`.
- **RIFE** receives `-m <models_dir>/<model>`, i.e. the model's own subfolder.

The models directory defaults to the managed `models/` dir but can be overridden
via the `models_dir` key in the config's `extra` map (useful for pointing at an
externally installed model set). Without a models directory, RIFE falls back to
passing the bare model name as the path.

---

## 6. Provisioning (`init`)

1. Detect OS + architecture.
2. Create the application directories.
3. Resolve per-platform release assets for FFmpeg, Real-ESRGAN, RIFE.
4. Download each asset (streamed, with a progress bar) and extract it into `bin/`.
5. Save the config.
6. Run `doctor` and print the report.

The HTTP client is injected, so provisioning is fully unit-tested with fake
archives and no network access.

---

## 7. Testing strategy

- Pure logic (platform detection, config round-trips, fps/frame math, probe
  parsing) is tested directly.
- Command construction (FFmpeg, NCNN) is verified through a recording runner
  that captures argv without executing anything.
- Pipelines run end-to-end against fake FFmpeg + backend collaborators.
- The CLI is exercised with Typer's `CliRunner`, including a fully faked
  provisioning download.

Run `pytest`, `ruff check .`, and `black --check .` before committing.
