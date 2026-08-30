import subprocess
from pathlib import Path

import pytest
from PIL import Image

from toolkit import (
    OUTPUT_DIR,
    convert_format,
    remove_background,
    resize_image,
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
