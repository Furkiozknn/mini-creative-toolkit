"""inspect_media, optimize_media, and the three upscalers."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mini_creative_toolkit.config import Config
from mini_creative_toolkit.errors import InvalidInputError, ResourceLimitError
from mini_creative_toolkit.tools.inspect import inspect_media
from mini_creative_toolkit.tools.optimize import optimize_media
from mini_creative_toolkit.tools.upscale import (
    choose_upscale_method,
    upscale_image_auto,
    upscale_image_fast,
)

from helpers import needs_ffmpeg


def test_inspect_describes_an_image_without_writing_anything(config, png):
    before = list(config.output_dir.glob("*")) if config.output_dir.exists() else []
    info = inspect_media(str(png))
    assert info["kind"] == "image"
    assert (info["width"], info["height"]) == (120, 60)
    assert info["aspect_ratio"] == "2:1"
    assert info["has_alpha"] is True
    after = list(config.output_dir.glob("*")) if config.output_dir.exists() else []
    assert before == after


def test_inspect_reports_exif_presence(config, jpeg_with_exif):
    assert inspect_media(str(jpeg_with_exif))["has_exif"] is True


def test_inspect_reports_no_metadata_after_stripping(config, jpeg_with_exif):
    from mini_creative_toolkit.tools.image import strip_metadata

    stripped = strip_metadata(str(jpeg_with_exif))["output_path"]
    assert inspect_media(stripped)["has_exif"] is False


@needs_ffmpeg
def test_inspect_describes_a_video_including_both_codecs(config, video):
    info = inspect_media(str(video))
    assert info["kind"] == "video"
    assert info["video_codec"] == "h264"
    assert info["has_audio"] is True
    assert info["audio_codec"]
    assert info["duration_seconds"] == pytest.approx(3.0, abs=0.3)
    assert info["fps"] == pytest.approx(10.0, abs=0.1)


@needs_ffmpeg
def test_inspect_describes_audio(config, video, tmp_path):
    from mini_creative_toolkit.tools.video import extract_audio

    track = extract_audio(str(video), "wav")["output_path"]
    info = inspect_media(track)
    assert info["kind"] == "audio"
    assert info["sample_rate"] and info["channels"]
    assert info["has_video"] is False


def test_inspect_refuses_something_that_is_not_media(config, tmp_path):
    junk = tmp_path / "notes.txt"
    junk.write_text("just some words")
    with pytest.raises(InvalidInputError):
        inspect_media(str(junk))


@pytest.mark.parametrize("goal", ["web", "quality", "smallest", "social", "archive"])
def test_every_goal_produces_a_file_and_explains_itself(config, tmp_path, goal):
    source = tmp_path / "photo.png"
    img = Image.new("RGB", (300, 200))
    img.putdata([((x * 3) % 256, (y * 5) % 256, 128) for y in range(200) for x in range(300)])
    img.save(source)
    result = optimize_media(str(source), goal)
    assert Path(result["output_path"]).exists()
    assert result["operations"]
    assert result["quality_notes"]


def test_archive_stays_lossless(config, png):
    result = optimize_media(str(png), "archive")
    assert result["format"] == "PNG"
    assert not any("lossy" in n.lower() for n in result["quality_notes"])


def test_optimize_does_not_silently_discard_transparency(config, png_with_alpha):
    """'web' must not flatten alpha behind the caller's back - it picks a
    format that keeps it instead."""
    result = optimize_media(str(png_with_alpha), "web")
    assert result["format"] in ("WEBP", "PNG")


def test_optimize_says_so_when_the_result_is_not_smaller(config, tmp_path):
    tiny = tmp_path / "tiny.png"
    Image.new("RGB", (4, 4), (0, 0, 0)).save(tiny)
    result = optimize_media(str(tiny), "quality")
    if result["output_size"] >= result["input_size"]:
        assert any("not smaller" in n for n in result["quality_notes"])


def test_optimize_can_fit_to_a_preset_and_carries_its_disclaimer(config, tmp_path):
    source = tmp_path / "big.png"
    Image.new("RGB", (2000, 1500), (10, 20, 30)).save(source)
    result = optimize_media(str(source), "social", preset="square")
    assert result["actual_width"] <= 1080 and result["actual_height"] <= 1080
    assert any("not a guarantee" in n for n in result["quality_notes"])


def test_optimize_rejects_an_unknown_goal(config, png):
    with pytest.raises(InvalidInputError):
        optimize_media(str(png), "make it pop")


def test_optimize_refuses_audio_with_a_useful_message(config, tmp_path, video):
    from mini_creative_toolkit.tools.video import extract_audio

    track = extract_audio(str(video), "wav")["output_path"]
    with pytest.raises(InvalidInputError, match="images and video"):
        optimize_media(track, "web")


@needs_ffmpeg
def test_optimize_handles_video_and_reports_the_trade(config, video):
    result = optimize_media(str(video), "smallest")
    assert result["kind"] == "video"
    assert any("lossy" in n.lower() for n in result["quality_notes"])


@pytest.mark.parametrize("scale", [2, 3, 4])
def test_fsrcnn_upscales_by_exactly_the_requested_factor(config, tmp_path, scale):
    source = tmp_path / "small.png"
    Image.new("RGB", (30, 20), (200, 30, 30)).save(source)
    result = upscale_image_fast(str(source), scale)
    assert (result["actual_width"], result["actual_height"]) == (30 * scale, 20 * scale)


def test_fsrcnn_refuses_a_scale_it_has_no_weights_for(config, png):
    with pytest.raises(InvalidInputError, match="x8 model|one of"):
        upscale_image_fast(str(png), 8)


def test_fsrcnn_never_claims_real_esrgan_quality(config, tmp_path):
    source = tmp_path / "small.png"
    Image.new("RGB", (20, 20), (5, 5, 5)).save(source)
    note = upscale_image_fast(str(source), 2)["quality_note"]
    assert "does not hallucinate" in note


def test_auto_explains_which_method_it_picked_and_why(config, tmp_path):
    source = tmp_path / "small.png"
    Image.new("RGB", (24, 24), (7, 7, 7)).save(source)
    result = upscale_image_auto(str(source), 4)
    assert result["selected_method"] in ("lanczos", "fsrcnn", "real-esrgan")
    assert len(result["selection_reason"]) > 30
    assert result["method_ranking"] == ["lanczos", "fsrcnn", "real-esrgan"]


def test_auto_uses_lanczos_for_an_enlargement_too_small_to_benefit(config):
    method, reason = choose_upscale_method(1.2, config)
    assert method == "lanczos"
    assert "1.2x" in reason


def test_auto_prefers_real_esrgan_only_when_both_conditions_hold(monkeypatch, config, tmp_path):
    """Configured Upscayl alone is not enough - without a discrete GPU it is
    unusable, and picking it anyway would hang for minutes."""
    binary = tmp_path / "upscayl-bin"
    binary.write_text("#!/bin/sh\n")
    models = tmp_path / "models"
    models.mkdir()
    cfg = Config(output_dir=config.output_dir, upscayl_bin=binary, upscayl_models=models)

    monkeypatch.setenv("MCT_FORCE_NO_GPU", "1")
    assert choose_upscale_method(4, cfg)[0] == "fsrcnn"

    monkeypatch.delenv("MCT_FORCE_NO_GPU")
    monkeypatch.setenv("MCT_FORCE_GPU", "1")
    assert choose_upscale_method(4, cfg)[0] == "real-esrgan"


def test_auto_falls_back_to_lanczos_when_fsrcnn_has_no_model_for_the_scale(config, tmp_path):
    source = tmp_path / "small.png"
    Image.new("RGB", (16, 16), (3, 3, 3)).save(source)
    result = upscale_image_auto(str(source), 5)
    assert result["selected_method"] == "lanczos"
    assert "x5 model" in result["selection_reason"]
    assert (result["actual_width"], result["actual_height"]) == (80, 80)


def test_upscaling_respects_the_output_pixel_budget(config, tmp_path):
    """The budget is checked against the *output* size, not just the input -
    a 4x upscale of a large image is where this actually bites."""
    source = tmp_path / "medium.png"
    Image.new("RGB", (200, 200), (1, 1, 1)).save(source)
    tight = Config(output_dir=config.output_dir, max_image_pixels=100_000)
    with pytest.raises(ResourceLimitError):
        upscale_image_fast(str(source), 4, config=tight)


def test_upscale_image_without_upscayl_fails_only_that_tool(config, png):
    """Every other tool must keep working when Upscayl is absent."""
    from mini_creative_toolkit.errors import ModelUnavailableError
    from mini_creative_toolkit.tools.upscale import upscale_image

    with pytest.raises(ModelUnavailableError) as excinfo:
        upscale_image(str(png), 4)
    assert "UPSCAYL_BIN_PATH" in excinfo.value.message
    assert "upscale_image_fast" in excinfo.value.message
    assert upscale_image_fast(str(png), 2)["output_path"]
