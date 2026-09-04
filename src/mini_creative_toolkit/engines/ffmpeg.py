"""Every ffmpeg and ffprobe invocation in this project goes through here.

Two rules, enforced structurally rather than by convention:

1. ``shell=True`` is never used, and no caller-supplied value is ever
   formatted into a command string. Commands are argument *lists*, and the
   binary path comes from ``shutil.which``, not from the caller.
2. Input paths are always absolute (``paths.resolve_input`` guarantees it),
   so they begin with ``/`` and can never be re-read by ffmpeg as an option.
   Values that are not paths - timestamps, dimensions, codec names - go
   through ``validation`` first, which constrains them to shapes that cannot
   start with ``-``.

Everything else here is about failure: a timeout so a malformed input cannot
hang the server forever, and a stderr tail kept as ``detail`` so the caller
gets one useful sentence instead of forty kilobytes of ffmpeg banner.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from ..config import Config, get_config
from ..errors import ExternalToolError, InvalidInputError, MissingDependencyError
from ..log import get_logger

logger = get_logger(__name__)

#: How much of ffmpeg's stderr to keep for diagnostics. The banner alone is
#: over a kilobyte, and the actual error is always at the end.
STDERR_TAIL = 2000


def find(binary: str) -> str:
    path = shutil.which(binary)
    if path is None:
        raise MissingDependencyError(
            f"{binary} was not found on PATH. Install ffmpeg (which provides both "
            f"ffmpeg and ffprobe) and make sure it is on PATH; on Debian/Ubuntu: "
            f"'sudo apt-get install ffmpeg', on macOS: 'brew install ffmpeg'."
        )
    return path


def available(binary: str) -> bool:
    return shutil.which(binary) is not None


def _check_args(args: Sequence[str]) -> list[str]:
    out = []
    for i, arg in enumerate(args):
        if not isinstance(arg, str):
            raise InvalidInputError(f"ffmpeg argument {i} is {type(arg).__name__}, expected str")
        if "\x00" in arg:
            raise InvalidInputError(f"ffmpeg argument {i} contains a NUL byte")
        out.append(arg)
    return out


def run_ffmpeg(args: Sequence[str], config: Config | None = None, what: str = "operation") -> str:
    """Run ffmpeg with ``-y -nostdin`` and the given argument list.

    ``-nostdin`` matters for an MCP stdio server: without it ffmpeg reads the
    terminal, and in a server whose stdin is the JSON-RPC channel that means
    eating protocol bytes.
    """
    config = config or get_config()
    binary = find("ffmpeg")
    command = [binary, "-y", "-nostdin", "-loglevel", "error", *_check_args(args)]
    logger.debug("ffmpeg %s: %s", what, " ".join(command[1:]))
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=config.subprocess_timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        raise ExternalToolError(
            f"ffmpeg timed out after {config.subprocess_timeout_seconds:g}s during {what}. "
            f"Raise MCT_SUBPROCESS_TIMEOUT if this input legitimately takes longer."
        ) from None
    except OSError as exc:
        raise ExternalToolError(f"Could not run ffmpeg: {exc}") from None
    if proc.returncode != 0:
        raise ExternalToolError(
            f"ffmpeg failed during {what} (exit {proc.returncode}). "
            f"Run with MCT_LOG_LEVEL=verbose for the full log.",
            detail=proc.stderr[-STDERR_TAIL:],
        )
    return proc.stderr


def probe(path: Path, config: Config | None = None) -> dict:
    """``ffprobe -show_format -show_streams`` as parsed JSON."""
    config = config or get_config()
    binary = find("ffprobe")
    command = [
        binary, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    try:
        proc = subprocess.run(
            command, capture_output=True, text=True, timeout=min(120.0, config.subprocess_timeout_seconds)
        )
    except subprocess.TimeoutExpired:
        raise ExternalToolError(f"ffprobe timed out inspecting {path.name}") from None
    except OSError as exc:
        raise ExternalToolError(f"Could not run ffprobe: {exc}") from None
    if proc.returncode != 0:
        raise ExternalToolError(
            f"ffprobe could not read {path.name}. It may not be a media file this "
            f"ffmpeg build understands.",
            detail=proc.stderr[-STDERR_TAIL:],
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ExternalToolError(f"ffprobe returned output that is not JSON: {exc}") from None


def duration_seconds(path: Path, config: Config | None = None) -> float | None:
    """Container duration, or ``None`` when the container does not carry one."""
    info = probe(path, config)
    raw = info.get("format", {}).get("duration")
    if raw is None:
        for stream in info.get("streams", []):
            raw = stream.get("duration")
            if raw is not None:
                break
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def streams_by_type(info: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for stream in info.get("streams", []):
        grouped.setdefault(stream.get("codec_type", "unknown"), []).append(stream)
    return grouped


def parse_fraction(raw: object) -> float | None:
    """ffprobe reports frame rates as ``"30000/1001"``."""
    if not isinstance(raw, str) or "/" not in raw:
        try:
            return float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
    num, _, den = raw.partition("/")
    try:
        numerator, denominator = float(num), float(den)
    except ValueError:
        return None
    if denominator == 0:
        return None
    return numerator / denominator
