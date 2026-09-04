"""Optional Real-ESRGAN upscaling through Upscayl's bundled Vulkan binary.

Nothing about this is bundled with this repository: neither the binary nor
the models are redistributed here, and neither is downloaded automatically.
Both locations come from environment variables the user sets deliberately,
which is the only mechanism - the hardcoded Windows path that used to live
in ``toolkit.py`` is gone.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import Config, get_config
from ..errors import ExternalToolError, ModelUnavailableError
from ..log import get_logger
from ..validation import require_name, require_positive_int

logger = get_logger(__name__)

SUPPORTED_SCALES = (2, 3, 4)


def locations(config: Config | None = None) -> tuple[Path | None, Path | None]:
    config = config or get_config()
    return config.upscayl_bin, config.upscayl_models


def is_configured(config: Config | None = None) -> bool:
    binary, models = locations(config)
    return bool(binary and binary.is_file() and models and models.is_dir())


def require_configured(config: Config | None = None) -> tuple[Path, Path]:
    binary, models = locations(config)
    if not binary:
        raise ModelUnavailableError(
            "UPSCAYL_BIN_PATH is not set. This tool reuses a local Upscayl install; "
            "point UPSCAYL_BIN_PATH at its upscayl-bin executable and "
            "UPSCAYL_MODELS_PATH at its resources/models directory. Nothing is "
            "downloaded automatically. If you do not have Upscayl, use "
            "upscale_image_fast instead - it is CPU-only and needs no setup."
        )
    if not binary.is_file():
        raise ModelUnavailableError(
            f"UPSCAYL_BIN_PATH points at {binary}, which is not a file."
        )
    if not models:
        raise ModelUnavailableError(
            "UPSCAYL_MODELS_PATH is not set. Point it at Upscayl's resources/models "
            "directory."
        )
    if not models.is_dir():
        raise ModelUnavailableError(
            f"UPSCAYL_MODELS_PATH points at {models}, which is not a directory."
        )
    return binary, models


def upscale(source: Path, destination: Path, scale: int, model: str, config: Config | None = None) -> None:
    config = config or get_config()
    binary, models = require_configured(config)
    scale = require_positive_int(scale, "scale")
    if scale not in SUPPORTED_SCALES:
        raise ModelUnavailableError(
            f"Upscayl models are built for scales {SUPPORTED_SCALES}, got {scale}."
        )
    # A model name reaches argv, so it is constrained to a bare identifier -
    # no slashes, no dots, nothing that could be read as an option or escape
    # the models directory.
    model = require_name(model, "model")

    command = [
        str(binary),
        "-i", str(source),
        "-o", str(destination),
        "-m", str(models),
        "-n", model,
        "-s", str(scale),
    ]
    logger.info("upscale_image: running upscayl-bin (model=%s, scale=%d)", model, scale)
    try:
        proc = subprocess.run(
            command, capture_output=True, text=True, timeout=config.subprocess_timeout_seconds
        )
    except subprocess.TimeoutExpired:
        raise ExternalToolError(
            f"upscayl-bin timed out after {config.subprocess_timeout_seconds:g}s. On "
            f"integrated graphics this is expected - use upscale_image_fast, or raise "
            f"MCT_SUBPROCESS_TIMEOUT."
        ) from None
    except OSError as exc:
        raise ExternalToolError(f"Could not run upscayl-bin: {exc}") from None
    if proc.returncode != 0:
        raise ExternalToolError(
            f"upscayl-bin failed (exit {proc.returncode}). Check that the model name "
            f"{model!r} exists in {models}.",
            detail=proc.stderr[-2000:],
        )
