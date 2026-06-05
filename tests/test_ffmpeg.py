"""Tests for the FFmpeg/FFprobe wrapper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelflow.ffmpeg import FFmpeg, VideoMetadata, _format_fps, _parse_fraction
from tests.conftest import RecordingRunner

PROBE_JSON = json.dumps(
    {
        "format": {"duration": "10.0"},
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "30000/1001",
                "nb_frames": "300",
            },
            {"codec_type": "audio"},
        ],
    }
)


def test_parse_fraction() -> None:
    assert _parse_fraction("30000/1001") == pytest.approx(29.97, abs=0.01)
    assert _parse_fraction("0/0") == 0.0
    assert _parse_fraction(None) == 0.0


def test_format_fps_compacts_integers() -> None:
    assert _format_fps(30.0) == "30"
    assert _format_fps(29.97).startswith("29.97")


def test_probe_parses_metadata() -> None:
    runner = RecordingRunner(stdout=PROBE_JSON)
    ff = FFmpeg(runner=runner)
    meta = ff.probe("clip.mp4")
    assert isinstance(meta, VideoMetadata)
    assert meta.width == 1920
    assert meta.height == 1080
    assert meta.frame_count == 300
    assert meta.has_audio
    assert meta.resolution == "1920x1080"
    assert runner.calls[0][0] == "ffmpeg" or "ffprobe" in runner.calls[0][0]


def test_probe_derives_frame_count_from_duration() -> None:
    payload = json.dumps(
        {
            "format": {"duration": "2.0"},
            "streams": [
                {
                    "codec_type": "video",
                    "width": 100,
                    "height": 100,
                    "avg_frame_rate": "25/1",
                }
            ],
        }
    )
    ff = FFmpeg(runner=RecordingRunner(stdout=payload))
    meta = ff.probe("x.mp4")
    assert meta.frame_count == 50
    assert not meta.has_audio


def test_probe_without_video_stream_raises() -> None:
    payload = json.dumps({"streams": [{"codec_type": "audio"}]})
    ff = FFmpeg(runner=RecordingRunner(stdout=payload))
    with pytest.raises(ValueError, match="No video stream"):
        ff.probe("audio.mp3")


def test_extract_frames_builds_command(tmp_path: Path) -> None:
    runner = RecordingRunner()
    ff = FFmpeg(runner=runner)
    out = ff.extract_frames("in.mp4", tmp_path / "frames")
    assert out.is_dir()
    cmd = runner.calls[0]
    assert "-vsync" in cmd
    assert cmd[-1].endswith("frame_%08d.png")


def test_encode_frames_with_audio_maps_streams(tmp_path: Path) -> None:
    runner = RecordingRunner()
    ff = FFmpeg(runner=runner)
    ff.encode_frames(tmp_path / "frames", tmp_path / "out.mp4", 60.0, audio_source="in.mp4")
    cmd = runner.calls[0]
    assert "-map" in cmd
    assert "1:a:0?" in cmd
    assert "libx264" in cmd
    assert "60" in cmd


def test_encode_frames_without_audio_omits_mapping(tmp_path: Path) -> None:
    runner = RecordingRunner()
    ff = FFmpeg(runner=runner)
    ff.encode_frames(tmp_path / "frames", tmp_path / "out.mp4", 30.0)
    cmd = runner.calls[0]
    assert "-map" not in cmd


def test_list_frames_sorted(tmp_path: Path) -> None:
    for i in (3, 1, 2):
        (tmp_path / f"frame_{i:08d}.png").write_text("x")
    ff = FFmpeg()
    frames = ff.list_frames(tmp_path)
    assert [f.name for f in frames] == [
        "frame_00000001.png",
        "frame_00000002.png",
        "frame_00000003.png",
    ]
