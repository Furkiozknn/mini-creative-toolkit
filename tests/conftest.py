"""Shared fixtures.

Every test runs against a Config whose output directory is a fresh tmp_path,
so no test can see another's output and none of them write into the repo.
"""

from __future__ import annotations

import subprocess

import pytest
from PIL import Image

from helpers import FFMPEG

from mini_creative_toolkit.config import Config, reset_config, set_config


@pytest.fixture
def config(tmp_path) -> Config:
    """A per-test Config, installed as the process-wide one for the test."""
    cfg = Config(output_dir=tmp_path / "output")
    set_config(cfg)
    yield cfg
    reset_config()


@pytest.fixture
def outdir(config) -> "object":
    return config.output_dir


@pytest.fixture
def png(tmp_path):
    path = tmp_path / "sample.png"
    Image.new("RGBA", (120, 60), (200, 40, 40, 255)).save(path)
    return path


@pytest.fixture
def png_with_alpha(tmp_path):
    path = tmp_path / "alpha.png"
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for x in range(32):
        for y in range(32):
            img.putpixel((x, y), (10, 200, 90, 255))
    img.save(path)
    return path


@pytest.fixture
def jpeg_with_exif(tmp_path):
    path = tmp_path / "exif.jpg"
    img = Image.new("RGB", (48, 32), (10, 20, 30))
    exif = img.getexif()
    exif[271] = "TestCamera"  # Make
    exif[272] = "TestModel"  # Model
    img.save(path, exif=exif)
    return path


@pytest.fixture(scope="session")
def _video_source(tmp_path_factory):
    if not FFMPEG:
        pytest.skip("ffmpeg is not installed")
    path = tmp_path_factory.mktemp("media") / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=3:size=160x120:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", "-shortest", str(path)],
        capture_output=True, check=True,
    )
    return path


@pytest.fixture(scope="session")
def _silent_video_source(tmp_path_factory):
    if not FFMPEG:
        pytest.skip("ffmpeg is not installed")
    path = tmp_path_factory.mktemp("media") / "silent.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=96x64:rate=10",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, check=True,
    )
    return path


@pytest.fixture
def video(_video_source):
    return _video_source


@pytest.fixture
def silent_video(_silent_video_source):
    return _silent_video_source
