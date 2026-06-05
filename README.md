# PixelFlow

Cross-platform AI video enhancement CLI for video upscaling, image upscaling, frame interpolation, and video restoration. PixelFlow uses Real-ESRGAN, RIFE, and FFmpeg to improve video quality, increase video resolution, generate high-FPS video, and automate AI-powered video processing workflows on macOS, Linux, and Windows.

**Upscale. Interpolate. Enhance.**

## AI Video Upscaling & Frame Interpolation

PixelFlow is an open-source command-line tool for:

- AI video upscaling
- AI image upscaling
- Video frame interpolation
- 30 FPS to 60 FPS conversion
- 60 FPS to 120 FPS conversion
- Video enhancement and restoration
- Batch video processing
- Automated video workflows

Powered by:

- Real-ESRGAN for image and video upscaling
- RIFE for frame interpolation and FPS boosting
- FFmpeg for video decoding, encoding, and media processing

Ideal for content creators, developers, video engineers, AI enthusiasts, and anyone looking to enhance videos using open-source AI models.

---

## Install

PixelFlow is a Python 3.12+ package. For everyday use, install it as an isolated
CLI with [pipx](https://pipx.pypa.io/):

```bash
pipx install pixelflow
```

Or into an environment with pip:

```bash
pip install pixelflow
```

Then provision the external tools (FFmpeg, Real-ESRGAN, RIFE) for your platform:

```bash
pixelflow init
pixelflow doctor   # verify everything is ready
```

`doctor` prints a report like:

```text
FFmpeg          OK
FFprobe         OK
Real-ESRGAN     OK
RIFE            OK
Backend         OK    ncnn
Platform        OK    macOS arm64
Temp directory  OK
```

## Usage

Common use cases include:

- Upscaling 720p videos to 1080p or 4K
- Converting 24 FPS, 30 FPS, or 60 FPS videos to higher frame rates
- Enhancing anime, gameplay recordings, screen recordings, and archived footage
- Automating video enhancement pipelines from the terminal

```bash
# Upscale a single image
pixelflow upscale-image input.png -o output.png

# Upscale a video 2× (audio preserved)
pixelflow upscale-video input.mp4 -o output.mp4 --scale 2

# Interpolate to 60 fps
pixelflow interpolate input.mp4 -o output.mp4 --fps 60

# Upscale and interpolate in one pass
pixelflow enhance-video input.mp4 -o output.mp4 --scale 2 --fps 60
```

State (downloaded binaries, models, cache) lives in an OS-appropriate
application directory; override it with the `PIXELFLOW_HOME` environment
variable. See [`docs/SPEC.md`](docs/SPEC.md) for the full specification.

## Development

```bash
# Create an environment and install with dev extras
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Quality gate
ruff check .
black --check .
pytest
```

## Packaging & publishing

### PyPI (pipx / pip)

The package builds with [hatchling](https://hatch.pypa.io/). To cut a release:

```bash
# 1. Bump the version in pyproject.toml and update CHANGELOG.md
# 2. Build the sdist and wheel
python -m build            # produces dist/*.tar.gz and dist/*.whl

# 3. Upload to PyPI
python -m twine upload dist/*
```

### Standalone binaries (PyInstaller)

Produce a self-contained executable per platform:

```bash
pyinstaller --onefile --name pixelflow pixelflow/cli.py
```

Build on each target OS (cross-compilation is not supported) to produce:

```text
pixelflow-macos-arm64
pixelflow-linux-x64
pixelflow-windows-x64.exe
```

### Homebrew (macOS / Linux)

Publish a formula to a tap that downloads the release tarball and installs the
`pixelflow` entry point:

```ruby
class Pixelflow < Formula
  desc "Cross-platform AI video enhancement CLI"
  homepage "https://github.com/pixelflow/pixelflow"
  url "https://files.pythonhosted.org/.../pixelflow-0.1.0.tar.gz"
  sha256 "<sha256>"
  depends_on "python@3.12"
  # ... resource/install blocks ...
end
```

Then `brew install pixelflow/tap/pixelflow`.

### Winget (Windows)

Submit a manifest to
[microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs) referencing
the PyInstaller `.exe` release asset, then `winget install PixelFlow.PixelFlow`.

## License

PixelFlow is an open-source AI video enhancement project focused on video upscaling, image upscaling, frame interpolation, and cross-platform video processing.

See [LICENSE](LICENSE).
