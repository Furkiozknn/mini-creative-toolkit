"""Helpers shared between test modules.

Not in conftest.py: pytest imports conftest specially, so `from .conftest
import x` fails with "attempted relative import with no known parent package"
in a rootdir-inserted (non-package) test layout.
"""

from __future__ import annotations

import shutil

import pytest

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

needs_ffmpeg = pytest.mark.skipif(
    not (FFMPEG and FFPROBE), reason="ffmpeg/ffprobe are not installed"
)
