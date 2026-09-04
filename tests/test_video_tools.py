"""End-to-end video/audio tests against real ffmpeg-generated fixtures."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mini_creative_toolkit.engines import ffmpeg
from mini_creative_toolkit.errors import (
    ExternalToolError,
    InvalidInputError,
    MissingDependencyError,
    ResourceLimitError,
)
from mini_creative_toolkit.media_info import describe
from mini_creative_toolkit.tools.video import (
    extract_audio,
    video_compress,
    video_resize,
    video_thumbnail,
    video_to_gif,
    video_trim,
)

from helpers import needs_ffmpeg

pytestmark = needs_ffmpeg


def _duration(path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(proc.stdout.strip())


def test_thumbnail_produces_a_real_image(config, video):
    result = video_thumbnail(str(video), "00:00:01")
    assert Path(result["output_path"]).stat().st_size > 0
    assert describe(Path(result["output_path"]), config)["kind"] == "image"


@pytest.mark.parametrize("stamp", ["-ss", "1; rm -rf /", "$(id)", "../../etc/passwd", "-i"])
def test_thumbnail_refuses_a_timestamp_that_could_be_read_as_an_option(config, video, stamp):
    with pytest.raises(InvalidInputError):
        video_thumbnail(str(video), stamp)


def test_gif_is_produced_and_leaves_no_palette_behind(config, video):
    result = video_to_gif(str(video), "00:00:00", 1.0, 8, 120)
    assert Path(result["output_path"]).suffix == ".gif"
    leftovers = list(config.output_dir.glob("tmp-palette-*"))
    assert leftovers == [], f"palette files survived: {leftovers}"


def test_gif_cleans_up_the_palette_even_when_the_second_pass_fails(config, video, monkeypatch):
    """The palette is an intermediate; a crash between the two passes must not
    leave it lying in the output directory for the user to wonder about."""
    real = ffmpeg.run_ffmpeg
    calls = {"n": 0}

    def flaky(args, cfg=None, what="operation"):
        calls["n"] += 1
        if calls["n"] == 2:
            raise ExternalToolError("simulated encoder failure")
        return real(args, cfg, what)

    monkeypatch.setattr("mini_creative_toolkit.tools.video.ffmpeg.run_ffmpeg", flaky)
    with pytest.raises(ExternalToolError):
        video_to_gif(str(video), "00:00:00", 1.0, 8, 120)
    assert list(config.output_dir.glob("tmp-palette-*")) == []
    assert list(config.output_dir.glob("*.part-*")) == []
    assert list(config.output_dir.glob("clip-*.gif")) == []


def test_gif_refuses_a_frame_count_that_would_be_absurd(config, video):
    with pytest.raises(ResourceLimitError, match="frames"):
        video_to_gif(str(video), "00:00:00", duration=30.0, fps=50, width=480)


@pytest.mark.parametrize("kwargs", [
    {"duration": 0}, {"duration": -1}, {"fps": 0}, {"width": 0}, {"fps": 500},
])
def test_gif_rejects_out_of_range_arguments(config, video, kwargs):
    with pytest.raises(InvalidInputError):
        video_to_gif(str(video), "00:00:00", **{"duration": 1.0, "fps": 8, "width": 80, **kwargs})


def test_trim_produces_roughly_the_requested_duration(config, video):
    result = video_trim(str(video), "00:00:00", 1.5)
    assert abs(_duration(result["output_path"]) - 1.5) < 0.5
    assert result["method"] in ("stream-copy", "re-encode")


def test_trim_reports_which_method_it_used(config, video):
    """Stream copy can only cut on keyframes. When it lands short the clip is
    re-encoded instead, and the caller is told - silently returning a clip of
    the wrong length is the failure mode this replaces."""
    result = video_trim(str(video), "00:00:01", 1.0)
    assert result["method"] in ("stream-copy", "re-encode")
    assert result["actual_duration"] is not None


def test_trim_rejects_a_non_positive_duration(config, video):
    with pytest.raises(InvalidInputError):
        video_trim(str(video), "00:00:00", 0)


def test_video_resize_produces_even_dimensions(config, video):
    """H.264 requires even dimensions; an odd target must not fail obscurely."""
    result = video_resize(str(video), 81)
    assert result["actual_width"] % 2 == 0
    assert result["actual_height"] % 2 == 0


def test_video_compress_is_honest_when_the_output_grew(config, video):
    result = video_compress(str(video), crf=30)
    notes = " ".join(result["quality_notes"])
    assert "lossy" in notes.lower()
    if result["output_size_bytes"] > result["input_size_bytes"]:
        assert "larger than the input" in notes


def test_video_compress_rejects_an_unknown_preset(config, video):
    with pytest.raises(InvalidInputError):
        video_compress(str(video), preset="turbo")


@pytest.mark.parametrize("fmt", ["mp3", "wav"])
def test_extract_audio_produces_a_real_track(config, video, fmt):
    result = extract_audio(str(video), fmt)
    out = Path(result["output_path"])
    assert out.suffix == f".{fmt}" and out.stat().st_size > 0
    assert describe(out, config)["kind"] == "audio"


def test_extract_audio_rejects_a_format_it_does_not_support(config, video):
    with pytest.raises(InvalidInputError):
        extract_audio(str(video), "ogg")


def test_extract_audio_says_so_when_there_is_no_audio(config, silent_video):
    """Previously this produced an empty file and reported success."""
    with pytest.raises(InvalidInputError, match="no audio"):
        extract_audio(str(silent_video), "mp3")


def test_thumbnail_says_so_when_there_is_no_video_stream(config, video, tmp_path):
    audio_only = tmp_path / "audio.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vn", "-acodec", "libmp3lame", str(audio_only)],
        capture_output=True, check=True,
    )
    with pytest.raises(InvalidInputError, match="no video"):
        video_thumbnail(str(audio_only))


def test_video_duration_limit_names_itself(config, video):
    from mini_creative_toolkit.config import Config

    tight = Config(output_dir=config.output_dir, max_video_duration_seconds=1.0)
    with pytest.raises(ResourceLimitError) as excinfo:
        video_thumbnail(str(video), config=tight)
    assert excinfo.value.limit_name == "MCT_MAX_VIDEO_DURATION"


def test_a_missing_ffmpeg_produces_an_actionable_error(monkeypatch):
    monkeypatch.setattr("mini_creative_toolkit.engines.ffmpeg.shutil.which", lambda name: None)
    with pytest.raises(MissingDependencyError) as excinfo:
        ffmpeg.find("ffmpeg")
    assert "PATH" in excinfo.value.message
    assert "apt-get install ffmpeg" in excinfo.value.message


def test_ffmpeg_failures_keep_the_log_out_of_the_message(config, tmp_path):
    """A forty-kilobyte ffmpeg log pasted into a model's context is worse than
    useless, so the tail lives in `detail` and only surfaces when verbose."""
    fake = tmp_path / "not-a-video.mp4"
    fake.write_bytes(b"\x00" * 4096)
    with pytest.raises(Exception) as excinfo:
        video_thumbnail(str(fake))
    error = excinfo.value
    if hasattr(error, "message"):
        assert len(error.message) < 400
