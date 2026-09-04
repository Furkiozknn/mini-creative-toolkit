"""End-to-end image tests against real generated files - no mocks."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mini_creative_toolkit.errors import (
    InvalidInputError,
    ResourceLimitError,
    UnsupportedFormatError,
)
from mini_creative_toolkit.tools.image import (
    add_watermark,
    compare_images,
    convert_format,
    create_contact_sheet,
    resize_image,
    strip_metadata,
)


def test_resize_fits_within_the_box_without_distorting(config, png):
    result = resize_image(str(png), 40, 40)
    assert (result["actual_width"], result["actual_height"]) == (40, 20)
    with Image.open(result["output_path"]) as img:
        assert img.size == (40, 20)


def test_resize_stretches_when_aspect_is_disabled(config, png):
    result = resize_image(str(png), 20, 40, keep_aspect=False)
    assert (result["actual_width"], result["actual_height"]) == (20, 40)


def test_resize_reports_both_requested_and_actual_dimensions(config, png):
    """The old API returned only a path, so a caller could not tell that
    keep_aspect had changed the result. Now it can."""
    result = resize_image(str(png), 40, 40)
    assert result["requested_height"] == 40
    assert result["actual_height"] == 20


@pytest.mark.parametrize("bad", [0, -5, 3.5, "40"])
def test_resize_rejects_nonsense_dimensions(config, png, bad):
    with pytest.raises(InvalidInputError):
        resize_image(str(png), bad, 40)


def test_resize_refuses_a_missing_file(config, tmp_path):
    with pytest.raises(InvalidInputError, match="No such file"):
        resize_image(str(tmp_path / "nope.png"), 10, 10)


def test_convert_to_jpeg_flattens_alpha_and_says_so(config, png_with_alpha):
    result = convert_format(str(png_with_alpha), "jpg")
    assert result["format"] == "JPEG"
    assert any("flatten" in note.lower() for note in result["notes"])
    with Image.open(result["output_path"]) as img:
        assert img.mode == "RGB"


def test_convert_honours_an_explicit_background_colour(config, png_with_alpha):
    result = convert_format(str(png_with_alpha), "jpg", background="#000000")
    with Image.open(result["output_path"]) as img:
        assert img.getpixel((60, 60))[0] < 40  # the transparent corner is black


def test_convert_to_webp_keeps_alpha(config, png_with_alpha):
    result = convert_format(str(png_with_alpha), "webp")
    with Image.open(result["output_path"]) as img:
        assert img.mode in ("RGBA", "LA")


def test_convert_rejects_a_format_nobody_has_heard_of(config, png):
    with pytest.raises(UnsupportedFormatError):
        convert_format(str(png), "jpeg2000ish")


def test_convert_quality_actually_changes_the_output_size(config, tmp_path):
    """A low quality that produced the same bytes would mean the argument was
    being ignored - which is the kind of silent no-op worth pinning."""
    source = tmp_path / "photo.png"
    img = Image.new("RGB", (256, 256))
    img.putdata([((x * 7) % 256, (y * 11) % 256, (x * y) % 256)
                 for y in range(256) for x in range(256)])
    img.save(source)
    low = convert_format(str(source), "jpg", quality=20)
    high = convert_format(str(source), "jpg", quality=95)
    assert low["output_size_bytes"] < high["output_size_bytes"]


def test_strip_metadata_removes_a_real_exif_tag(config, jpeg_with_exif):
    with Image.open(jpeg_with_exif) as original:
        assert original.getexif().get(271) == "TestCamera"
    result = strip_metadata(str(jpeg_with_exif))
    assert result["removed_exif"] is True
    with Image.open(result["output_path"]) as stripped:
        assert stripped.getexif().get(271) is None
        assert stripped.getexif().get(272) is None


def test_strip_metadata_preserves_the_pixels(config, jpeg_with_exif):
    result = strip_metadata(str(jpeg_with_exif))
    with Image.open(jpeg_with_exif) as a, Image.open(result["output_path"]) as b:
        assert a.size == b.size


def test_strip_metadata_reports_when_there_was_nothing_to_remove(config, png):
    result = strip_metadata(str(png))
    assert result["removed_exif"] is False


def test_watermark_changes_pixels_without_changing_size(config, png):
    result = add_watermark(str(png), "hi", opacity=1.0, font_size=16)
    with Image.open(png) as original, Image.open(result["output_path"]) as marked:
        assert marked.size == original.size
        assert marked.convert("RGB").tobytes() != original.convert("RGB").tobytes()


@pytest.mark.parametrize("position", sorted({"top-left", "top-right", "bottom-left", "bottom-right", "center"}))
def test_watermark_accepts_every_documented_position(config, png, position):
    assert add_watermark(str(png), "x", position=position)["position"] == position


def test_watermark_rejects_an_undocumented_position(config, png):
    with pytest.raises(InvalidInputError):
        add_watermark(str(png), "hi", position="middle")


@pytest.mark.parametrize("opacity", [-0.1, 1.5, "half"])
def test_watermark_rejects_out_of_range_opacity(config, png, opacity):
    with pytest.raises(InvalidInputError):
        add_watermark(str(png), "hi", opacity=opacity)


def test_watermark_refuses_text_carrying_terminal_escapes(config, png):
    with pytest.raises(InvalidInputError, match="control characters"):
        add_watermark(str(png), "\x1b[31mowned\x1b[0m")


def test_contact_sheet_tiles_every_readable_image(config, tmp_path):
    paths = []
    for i in range(5):
        p = tmp_path / f"tile{i}.png"
        Image.new("RGB", (40, 30), (i * 40, 60, 90)).save(p)
        paths.append(str(p))
    result = create_contact_sheet(paths, thumbnail_size=48, columns=3)
    assert result["tiled"] == 5
    assert result["rows"] == 2
    assert Path(result["output_path"]).exists()


def test_contact_sheet_skips_a_broken_file_instead_of_losing_the_sheet(config, tmp_path):
    good = tmp_path / "good.png"
    Image.new("RGB", (30, 30), (1, 2, 3)).save(good)
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"this is not a PNG")
    result = create_contact_sheet([str(good), str(broken)], thumbnail_size=32, columns=2)
    assert result["tiled"] == 1
    assert len(result["skipped"]) == 1
    assert "broken.png" in result["skipped"][0]["path"]


def test_contact_sheet_fails_clearly_when_nothing_is_readable(config, tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not a PNG at all")
    with pytest.raises(InvalidInputError, match="none of the supplied images|None of the supplied"):
        create_contact_sheet([str(broken)])


def test_compare_reports_byte_identity_exactly(config, tmp_path, png):
    copy = tmp_path / "copy.png"
    copy.write_bytes(png.read_bytes())
    result = compare_images(str(png), str(copy))
    assert result["identical_bytes"] is True
    assert result["mean_pixel_difference"] == 0.0


def test_compare_does_not_claim_forensic_certainty(config, tmp_path, png):
    other = tmp_path / "other.png"
    Image.new("RGB", (120, 60), (10, 220, 30)).save(other)
    result = compare_images(str(png), str(other))
    assert result["identical_bytes"] is False
    assert result["mean_pixel_difference"] > 8
    assert "not forensic" in result["caveat"]


def test_the_pixel_budget_refuses_a_decompression_bomb(config, tmp_path, monkeypatch):
    """A 60000x60000 PNG compresses to a few kilobytes and decodes to
    gigabytes. The header is checked before any pixel data is touched."""
    from mini_creative_toolkit.config import Config, set_config

    tight = Config(output_dir=config.output_dir, max_image_pixels=1000)
    set_config(tight)
    source = tmp_path / "big.png"
    Image.new("RGB", (200, 200), (0, 0, 0)).save(source)
    with pytest.raises(ResourceLimitError) as excinfo:
        resize_image(str(source), 10, 10, config=tight)
    assert excinfo.value.limit_name == "MCT_MAX_IMAGE_PIXELS"


def test_explicit_output_path_is_honoured(config, png, tmp_path):
    target = tmp_path / "chosen.png"
    result = resize_image(str(png), 30, 30, output_path=str(target))
    assert result["output_path"] == str(target)
    assert target.exists()


def test_explicit_output_path_will_not_clobber_without_permission(config, png, tmp_path):
    target = tmp_path / "chosen.png"
    target.write_bytes(b"precious")
    with pytest.raises(InvalidInputError, match="overwrite"):
        resize_image(str(png), 30, 30, output_path=str(target))
    assert target.read_bytes() == b"precious"
    resize_image(str(png), 30, 30, output_path=str(target), overwrite=True)
    assert target.read_bytes() != b"precious"


def test_an_operation_never_writes_over_its_own_input(config, png):
    result = resize_image(str(png), 30, 30)
    assert result["output_path"] != str(png)
    with Image.open(png) as original:
        assert original.size == (120, 60)
