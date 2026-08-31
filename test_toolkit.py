import subprocess
from pathlib import Path

import pytest
from PIL import Image

from toolkit import (
    OUTPUT_DIR,
    add_watermark,
    convert_format,
    extract_audio,
    remove_background,
    resize_image,
    strip_metadata,
    upscale_image_fast,
    video_thumbnail,
    video_to_gif,
    video_trim,
)


@pytest.fixture(scope="module")
def sample_image(tmp_path_factory):
    path = tmp_path_factory.mktemp("fixtures") / "sample.png"
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(path)
    return path


@pytest.fixture(scope="module")
def sample_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("fixtures") / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=3:size=160x120:rate=10",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, check=True,
    )
    return path


@pytest.fixture(scope="module")
def sample_video_with_audio(tmp_path_factory):
    path = tmp_path_factory.mktemp("fixtures") / "sample-audio.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", "-shortest", str(path)],
        capture_output=True, check=True,
    )
    return path


@pytest.fixture(scope="module")
def sample_image_with_exif(tmp_path_factory):
    path = tmp_path_factory.mktemp("fixtures") / "sample-exif.jpg"
    img = Image.new("RGB", (32, 32), (10, 20, 30))
    exif = img.getexif()
    exif[271] = "TestCamera"  # tag 271 = Make
    img.save(path, exif=exif)
    return path


def test_resize_image_keeps_aspect(sample_image):
    out = Path(resize_image(str(sample_image), 32, 32))
    assert out.exists()
    with Image.open(out) as img:
        assert max(img.size) <= 32


def test_resize_image_distorts_when_aspect_disabled(sample_image):
    out = Path(resize_image(str(sample_image), 20, 40, keep_aspect=False))
    with Image.open(out) as img:
        assert img.size == (20, 40)


def test_resize_image_rejects_non_positive_dimensions(sample_image):
    with pytest.raises(ValueError):
        resize_image(str(sample_image), 0, 10)


def test_resize_image_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        resize_image(str(OUTPUT_DIR / "does-not-exist.png"), 10, 10)


def test_convert_format_flattens_transparency_for_jpeg(sample_image):
    out = Path(convert_format(str(sample_image), "jpg"))
    assert out.suffix == ".jpg"
    with Image.open(out) as img:
        assert img.mode == "RGB"


def test_upscale_image_fast_scales_up(sample_image):
    out = Path(upscale_image_fast(str(sample_image), scale=4))
    assert out.exists()
    with Image.open(out) as img:
        assert img.size == (256, 256)  # 64x64 source * 4


def test_upscale_image_fast_rejects_unsupported_scale(sample_image):
    with pytest.raises(ValueError):
        upscale_image_fast(str(sample_image), scale=5)


def test_upscale_image_fast_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        upscale_image_fast(str(OUTPUT_DIR / "does-not-exist.png"))


def test_remove_background_produces_rgba_png(sample_image):
    out = Path(remove_background(str(sample_image)))
    assert out.exists()
    with Image.open(out) as img:
        assert img.mode == "RGBA"


def test_video_thumbnail_produces_image(sample_video):
    out = Path(video_thumbnail(str(sample_video), "00:00:00"))
    assert out.exists() and out.stat().st_size > 0


def test_video_to_gif_produces_animated_gif(sample_video):
    out = Path(video_to_gif(str(sample_video), "00:00:00", 1.0, 8, 120))
    assert out.suffix == ".gif" and out.exists()
    # the intermediate palette file must not survive a successful run
    assert not any(OUTPUT_DIR.glob("palette-*.png"))


def test_video_trim_produces_expected_duration(sample_video):
    out = Path(video_trim(str(sample_video), "00:00:00", 1.5))
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    )
    assert abs(float(result.stdout.strip()) - 1.5) < 0.5


def test_video_trim_rejects_non_positive_duration(sample_video):
    with pytest.raises(ValueError):
        video_trim(str(sample_video), "00:00:00", 0)


def test_strip_metadata_removes_exif(sample_image_with_exif):
    with Image.open(sample_image_with_exif) as original:
        assert original.getexif().get(271) == "TestCamera"

    out = Path(strip_metadata(str(sample_image_with_exif)))
    assert out.exists()
    with Image.open(out) as stripped:
        assert stripped.getexif().get(271) is None


def test_strip_metadata_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        strip_metadata(str(OUTPUT_DIR / "does-not-exist.png"))


def test_add_watermark_changes_pixels_and_keeps_size(sample_image):
    out = Path(add_watermark(str(sample_image), "hi", position="bottom-right", opacity=1.0, font_size=16))
    assert out.exists()
    with Image.open(sample_image) as original, Image.open(out) as watermarked:
        assert watermarked.size == original.size
        assert watermarked.tobytes() != original.tobytes()


def test_add_watermark_rejects_invalid_position(sample_image):
    with pytest.raises(ValueError):
        add_watermark(str(sample_image), "hi", position="middle")


def test_add_watermark_rejects_invalid_opacity(sample_image):
    with pytest.raises(ValueError):
        add_watermark(str(sample_image), "hi", opacity=1.5)


def test_add_watermark_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        add_watermark(str(OUTPUT_DIR / "does-not-exist.png"), "hi")


def test_extract_audio_produces_mp3(sample_video_with_audio):
    out = Path(extract_audio(str(sample_video_with_audio), "mp3"))
    assert out.suffix == ".mp3" and out.exists() and out.stat().st_size > 0


def test_extract_audio_produces_wav(sample_video_with_audio):
    out = Path(extract_audio(str(sample_video_with_audio), "wav"))
    assert out.suffix == ".wav" and out.exists() and out.stat().st_size > 0


def test_extract_audio_rejects_bad_format(sample_video_with_audio):
    with pytest.raises(ValueError):
        extract_audio(str(sample_video_with_audio), "ogg")


def test_extract_audio_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        extract_audio(str(OUTPUT_DIR / "does-not-exist.mp4"))
