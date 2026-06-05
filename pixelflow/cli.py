"""PixelFlow command-line interface.

Wires the Typer app to the pipelines, doctor, and provisioning logic. Command
bodies stay thin: they parse options, build dependencies from config, invoke the
relevant pipeline, and render the result. The reusable provisioning logic lives
in :func:`provision` so it can be tested with a fake HTTP client.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import Config
from .doctor import DoctorReport, run_doctor
from .downloader import Downloader, HttpClient, resolve_assets
from .pipelines import (
    Dependencies,
    build_dependencies,
    enhance_video,
    interpolate_video,
    upscale_image,
    upscale_video,
)
from .utils.paths import AppPaths, app_paths, detect_platform
from .utils.progress import RichProgressReporter

app = typer.Typer(
    name="pixelflow",
    help="PixelFlow — Upscale. Interpolate. Enhance.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"pixelflow {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the PixelFlow version and exit.",
    ),
) -> None:
    """PixelFlow root command."""


# -- provisioning ---------------------------------------------------------


def provision(
    client: HttpClient,
    *,
    paths: AppPaths | None = None,
    reporter: RichProgressReporter | None = None,
) -> Config:
    """Detect the platform, fetch tools, and write a fresh config.

    Returns the saved :class:`Config`. The HTTP client is injected so this is
    testable without hitting the network.
    """
    paths = (paths or app_paths()).ensure()
    platform = detect_platform()
    config = Config.for_platform(platform)

    downloader = Downloader(client, reporter=reporter)
    for asset in resolve_assets(platform):
        downloader.fetch_asset(asset, paths.cache_dir, paths.bin_dir)

    config.save(paths)
    return config


@app.command()
def init() -> None:
    """Provision FFmpeg and the AI backends, then run health checks."""
    import requests

    paths = app_paths()
    reporter = RichProgressReporter(console)
    console.print("[bold]Initialising PixelFlow[/bold]")
    try:
        provision(requests.Session(), paths=paths, reporter=reporter)
    except Exception as exc:  # surfaced to the user, non-zero exit
        console.print(f"[red]init failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print("[green]Downloads complete.[/green]\n")
    _render_doctor(run_doctor(paths=paths))


@app.command()
def doctor() -> None:
    """Check that FFmpeg, the AI backends, and the GPU backend are ready."""
    report = run_doctor()
    _render_doctor(report)
    if not report.healthy:
        raise typer.Exit(code=1)


def _render_doctor(report: DoctorReport) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("Check", style="bold", no_wrap=True)
    table.add_column("Status")
    for check in report.checks:
        marker = "[green]OK[/green]" if check.ok else "[red]MISSING[/red]"
        table.add_row(check.name, f"{marker}  [dim]{check.detail}[/dim]")
    console.print(table)


# -- enhancement commands -------------------------------------------------


def _deps() -> Dependencies:
    return build_dependencies(reporter=RichProgressReporter(console))


@app.command("upscale-image")
def upscale_image_cmd(
    source: Path = typer.Argument(..., help="Input image."),
    output: Path = typer.Option(..., "-o", "--output", help="Output image."),
    scale: int | None = typer.Option(None, "--scale", help="Upscale factor (default from config)."),
    model: str | None = typer.Option(None, "--model", help="Real-ESRGAN model name."),
) -> None:
    """Upscale a single image with Real-ESRGAN."""
    deps = _deps()
    result = upscale_image(
        source, output, backend=deps.backend, config=deps.config, scale=scale, model=model
    )
    console.print(f"[green]Wrote[/green] {result.output}")


@app.command("upscale-video")
def upscale_video_cmd(
    source: Path = typer.Argument(..., help="Input video."),
    output: Path = typer.Option(..., "-o", "--output", help="Output video."),
    scale: int | None = typer.Option(None, "--scale", help="Upscale factor (default from config)."),
    model: str | None = typer.Option(None, "--model", help="Real-ESRGAN model name."),
) -> None:
    """Upscale every frame of a video, preserving fps and audio."""
    deps = _deps()
    result = upscale_video(source, output, deps=deps, scale=scale, model=model)
    console.print(f"[green]Wrote[/green] {result.output} ({result.frames_processed} frames)")


@app.command()
def interpolate(
    source: Path = typer.Argument(..., help="Input video."),
    output: Path = typer.Option(..., "-o", "--output", help="Output video."),
    fps: float = typer.Option(..., "--fps", help="Target frame rate."),
    model: str | None = typer.Option(None, "--model", help="RIFE model name."),
) -> None:
    """Interpolate a video to a higher frame rate with RIFE."""
    deps = _deps()
    result = interpolate_video(source, output, deps=deps, target_fps=fps, model=model)
    console.print(f"[green]Wrote[/green] {result.output} ({result.frames_processed} frames)")


@app.command("enhance-video")
def enhance_video_cmd(
    source: Path = typer.Argument(..., help="Input video."),
    output: Path = typer.Option(..., "-o", "--output", help="Output video."),
    scale: int | None = typer.Option(None, "--scale", help="Upscale factor (default from config)."),
    fps: float = typer.Option(..., "--fps", help="Target frame rate."),
) -> None:
    """Upscale and interpolate a video in one pass."""
    deps = _deps()
    result = enhance_video(source, output, deps=deps, target_fps=fps, scale=scale)
    console.print(f"[green]Wrote[/green] {result.output} ({result.frames_processed} frames)")


if __name__ == "__main__":
    app()
