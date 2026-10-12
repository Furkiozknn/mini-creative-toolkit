"""Helpers shared between test modules.

Not in conftest.py: pytest imports conftest specially, so `from .conftest
import x` fails with "attempted relative import with no known parent package"
in a rootdir-inserted (non-package) test layout.
"""

from __future__ import annotations

import os
import shutil

import pytest

def child_env(tmp_path, **extra) -> dict:
    """A deliberately small environment for a server subprocess.

    On Windows a child started with only PATH cannot load Winsock (asyncio dies
    with WinError 10106 before the first protocol byte), so SYSTEMROOT has to
    survive. It is not secret and not used by the toolkit.
    """
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp_path)}
    if os.environ.get("SYSTEMROOT"):
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    env.update(extra)
    return env


FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

needs_ffmpeg = pytest.mark.skipif(
    not (FFMPEG and FFPROBE), reason="ffmpeg/ffprobe are not installed"
)
