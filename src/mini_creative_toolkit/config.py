"""Configuration, read once from the environment.

Nothing here is required for normal use: every value has a working default.
The environment variables exist so a user can *tighten* the defaults (most
usefully ``MCT_ALLOWED_ROOTS``) or loosen a limit that their real workload
legitimately exceeds.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .errors import InvalidInputError

#: Where outputs land when ``MCT_OUTPUT_DIR`` is unset. Historically this was
#: ``output/`` next to ``toolkit.py``; that path is preserved so existing
#: setups keep finding their files in the same place.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _get(env: Mapping[str, str], name: str) -> str | None:
    raw = env.get(name)
    if raw is None:
        return None
    raw = raw.strip()
    return raw or None


def _env_int(env: Mapping[str, str], name: str, default: int, minimum: int = 1) -> int:
    raw = _get(env, name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise InvalidInputError(f"{name} must be an integer, got {raw!r}") from None
    if value < minimum:
        raise InvalidInputError(f"{name} must be >= {minimum}, got {value}")
    return value


def _env_float(env: Mapping[str, str], name: str, default: float, minimum: float = 0.0) -> float:
    raw = _get(env, name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise InvalidInputError(f"{name} must be a number, got {raw!r}") from None
    if value <= minimum:
        raise InvalidInputError(f"{name} must be > {minimum}, got {value}")
    return value


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = _get(env, name)
    if raw is None:
        return default
    lowered = raw.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise InvalidInputError(f"{name} must be one of {sorted(_TRUE | _FALSE)}, got {raw!r}")


def _env_roots(env: Mapping[str, str], name: str) -> tuple[Path, ...]:
    raw = _get(env, name)
    if raw is None:
        return ()
    roots = []
    for part in raw.split(os.pathsep):
        part = part.strip()
        if not part:
            continue
        root = Path(part).expanduser()
        try:
            root = root.resolve(strict=True)
        except OSError as exc:
            raise InvalidInputError(f"{name} entry {part!r} is not a usable directory: {exc}") from None
        if not root.is_dir():
            raise InvalidInputError(f"{name} entry {part!r} is not a directory")
        roots.append(root)
    return tuple(roots)


def _env_path(env: Mapping[str, str], name: str) -> Path | None:
    raw = _get(env, name)
    return Path(raw).expanduser() if raw else None


@dataclass(frozen=True)
class Config:
    """Resolved settings. Immutable; rebuild it to change anything."""

    output_dir: Path = DEFAULT_OUTPUT_DIR
    #: Empty means "no filesystem restriction beyond the OS's own". See
    #: SECURITY.md - this toolkit is not a sandbox, and pretending an empty
    #: default is one would be the dishonest choice.
    allowed_roots: tuple[Path, ...] = ()
    max_input_mb: float = 512.0
    max_output_mb: float = 1024.0
    max_image_pixels: int = 80_000_000
    max_video_duration_seconds: float = 3600.0
    max_video_width: int = 7680
    max_video_height: int = 7680
    max_batch_items: int = 200
    batch_concurrency: int = 4
    #: Concurrency ceiling for operations flagged CPU-heavy (background
    #: removal, super-resolution). Deliberately lower than the general cap.
    heavy_batch_concurrency: int = 2
    max_gif_duration_seconds: float = 30.0
    max_gif_fps: int = 50
    max_gif_width: int = 1920
    http_timeout_seconds: float = 60.0
    max_download_mb: float = 64.0
    log_level: str = "normal"
    upscayl_bin: Path | None = None
    upscayl_models: Path | None = None
    #: Restores the pre-2.0 behaviour of returning a bare path string from
    #: every tool instead of a structured dict. Off by default; see README.
    legacy_string_results: bool = False
    subprocess_timeout_seconds: float = 900.0

    @property
    def max_input_bytes(self) -> int:
        return int(self.max_input_mb * 1024 * 1024)

    @property
    def max_output_bytes(self) -> int:
        return int(self.max_output_mb * 1024 * 1024)

    @property
    def max_download_bytes(self) -> int:
        return int(self.max_download_mb * 1024 * 1024)

    @property
    def verbose(self) -> bool:
        return self.log_level == "verbose"

    def limits_dict(self) -> dict:
        return {
            "MCT_OUTPUT_DIR": str(self.output_dir),
            "MCT_ALLOWED_ROOTS": [str(p) for p in self.allowed_roots] or None,
            "MCT_MAX_INPUT_MB": self.max_input_mb,
            "MCT_MAX_OUTPUT_MB": self.max_output_mb,
            "MCT_MAX_IMAGE_PIXELS": self.max_image_pixels,
            "MCT_MAX_VIDEO_DURATION": self.max_video_duration_seconds,
            "MCT_MAX_VIDEO_WIDTH": self.max_video_width,
            "MCT_MAX_VIDEO_HEIGHT": self.max_video_height,
            "MCT_MAX_BATCH_ITEMS": self.max_batch_items,
            "MCT_BATCH_CONCURRENCY": self.batch_concurrency,
            "MCT_HEAVY_BATCH_CONCURRENCY": self.heavy_batch_concurrency,
            "MCT_HTTP_TIMEOUT": self.http_timeout_seconds,
            "MCT_MAX_DOWNLOAD_MB": self.max_download_mb,
            "MCT_LOG_LEVEL": self.log_level,
        }

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        env = os.environ if env is None else env

        log_level = (_get(env, "MCT_LOG_LEVEL") or "normal").lower()
        if log_level not in ("quiet", "normal", "verbose"):
            raise InvalidInputError(
                f"MCT_LOG_LEVEL must be quiet, normal or verbose, got {log_level!r}"
            )

        output_raw = _get(env, "MCT_OUTPUT_DIR")
        output_dir = Path(output_raw).expanduser() if output_raw else DEFAULT_OUTPUT_DIR

        return cls(
            output_dir=output_dir,
            allowed_roots=_env_roots(env, "MCT_ALLOWED_ROOTS"),
            max_input_mb=_env_float(env, "MCT_MAX_INPUT_MB", cls.max_input_mb),
            max_output_mb=_env_float(env, "MCT_MAX_OUTPUT_MB", cls.max_output_mb),
            max_image_pixels=_env_int(env, "MCT_MAX_IMAGE_PIXELS", cls.max_image_pixels),
            max_video_duration_seconds=_env_float(
                env, "MCT_MAX_VIDEO_DURATION", cls.max_video_duration_seconds
            ),
            max_video_width=_env_int(env, "MCT_MAX_VIDEO_WIDTH", cls.max_video_width),
            max_video_height=_env_int(env, "MCT_MAX_VIDEO_HEIGHT", cls.max_video_height),
            max_batch_items=_env_int(env, "MCT_MAX_BATCH_ITEMS", cls.max_batch_items),
            batch_concurrency=_env_int(env, "MCT_BATCH_CONCURRENCY", cls.batch_concurrency),
            heavy_batch_concurrency=_env_int(
                env, "MCT_HEAVY_BATCH_CONCURRENCY", cls.heavy_batch_concurrency
            ),
            http_timeout_seconds=_env_float(env, "MCT_HTTP_TIMEOUT", cls.http_timeout_seconds),
            max_download_mb=_env_float(env, "MCT_MAX_DOWNLOAD_MB", cls.max_download_mb),
            log_level=log_level,
            upscayl_bin=_env_path(env, "UPSCAYL_BIN_PATH"),
            upscayl_models=_env_path(env, "UPSCAYL_MODELS_PATH"),
            legacy_string_results=_env_bool(env, "MCT_LEGACY_STRING_RESULTS", False),
            subprocess_timeout_seconds=_env_float(
                env, "MCT_SUBPROCESS_TIMEOUT", cls.subprocess_timeout_seconds
            ),
        )


_cached: Config | None = None


def get_config() -> Config:
    """The process-wide config, built from the environment on first use."""
    global _cached
    if _cached is None:
        _cached = Config.from_env()
    return _cached


def set_config(config: Config | None) -> None:
    """Override (or, with ``None``, discard) the cached config.

    Tests use this; so does the CLI, which turns flags into a Config before
    calling into the same tool functions the MCP server calls.
    """
    global _cached
    _cached = config


def reset_config() -> None:
    set_config(None)
