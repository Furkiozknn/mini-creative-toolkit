"""Upscaling: three methods, and one tool that picks between them honestly.

The three are genuinely different, not three settings of one thing:

* **Lanczos** interpolates. It invents nothing. Instant.
* **FSRCNN** is a real (tiny) super-resolution network. Sharper edges than
  Lanczos, still invents no texture. Sub-second on CPU.
* **Real-ESRGAN** (via Upscayl) hallucinates plausible detail. Much better
  results, and needs a discrete GPU to be usable at all.

``upscale_image_auto`` chooses, and always says which it chose and why.
Nothing here ever claims the cheap one matches the expensive one.
"""

from __future__ import annotations

from PIL import Image

from .. import results
from ..config import Config, get_config
from ..engines import images, upscayl
from ..errors import InvalidInputError
from ..log import get_logger
from ..paths import OutputManager, resolve_input
from ..validation import require_name, require_positive_int

logger = get_logger(__name__)

QUALITY_ORDER = ("lanczos", "fsrcnn", "real-esrgan")

METHOD_NOTES = {
    "lanczos": "Interpolation only - no detail is added, edges stay soft.",
    "fsrcnn": (
        "A small pretrained super-resolution CNN. Sharper edges than Lanczos, but it "
        "does not hallucinate texture the way Real-ESRGAN does."
    ),
    "real-esrgan": (
        "Real-ESRGAN via Upscayl's Vulkan binary. The best quality available here, "
        "and the only method that invents plausible new detail."
    ),
}


def _context(config: Config | None = None) -> tuple[Config, OutputManager]:
    config = config or get_config()
    return config, OutputManager(config)


def upscale_image_fast(
    image_path: str,
    scale: int = 4,
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    config, manager = _context(config)
    source = resolve_input(image_path, config, "image_path")
    scale = require_positive_int(scale, "scale")
    if scale not in images.FSRCNN_SCALES:
        raise InvalidInputError(
            f"scale must be one of {list(images.FSRCNN_SCALES)} for FSRCNN, got {scale}. "
            f"The bundled weights are trained per scale factor; there is no x8 model."
        )

    width, height, _ = images.header_size(source)
    images.check_pixel_budget(width * scale, height * scale, source, config)

    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("upscaled-fast", "png", destination) as staged:
        out_w, out_h = images.fsrcnn_upscale(source, staged.tmp, scale)

    return results.build(
        "upscale_image_fast", staged.path, config=config,
        input=str(source), method="fsrcnn", scale=scale,
        input_width=width, input_height=height,
        actual_width=out_w, actual_height=out_h,
        quality_note=METHOD_NOTES["fsrcnn"],
    )


def upscale_image(
    image_path: str,
    scale: int = 4,
    model: str = "upscayl-standard-4x",
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    config, manager = _context(config)
    source = resolve_input(image_path, config, "image_path")
    scale = require_positive_int(scale, "scale")
    model = require_name(model, "model")

    width, height, _ = images.header_size(source)
    images.check_pixel_budget(width * scale, height * scale, source, config)

    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("upscaled", "png", destination) as staged:
        upscayl.upscale(source, staged.tmp, scale, model, config)

    out_w, out_h, _ = images.header_size(staged.path)
    return results.build(
        "upscale_image", staged.path, config=config,
        input=str(source), method="real-esrgan", model=model, scale=scale,
        input_width=width, input_height=height,
        actual_width=out_w, actual_height=out_h,
        quality_note=METHOD_NOTES["real-esrgan"],
    )


def choose_upscale_method(scale: float, config: Config | None = None) -> tuple[str, str]:
    """Decide which upscaler to use, and give the reason in plain words."""
    from ..capabilities import probe_environment

    config = config or get_config()
    env = probe_environment(config)

    if scale <= 1.0:
        return "lanczos", "The requested scale is not an enlargement, so no model is needed."
    if scale < 1.5:
        return (
            "lanczos",
            f"An enlargement of only {scale:g}x gains little from a super-resolution "
            f"model, so plain Lanczos resampling is used - it is instant and adds no "
            f"artefacts.",
        )
    if upscayl.is_configured(config) and env["discrete_gpu"]:
        return (
            "real-esrgan",
            f"Upscayl is configured and a discrete GPU was detected "
            f"({env['discrete_gpu_reason']}), so Real-ESRGAN is used - the best "
            f"quality available here.",
        )
    if not upscayl.is_configured(config):
        reason = "Upscayl is not configured (UPSCAYL_BIN_PATH / UPSCAYL_MODELS_PATH are unset or invalid)"
    else:
        reason = f"Upscayl is configured but {env['discrete_gpu_reason']}"
    return (
        "fsrcnn",
        f"FSRCNN was selected because {reason}. On integrated graphics Real-ESRGAN "
        f"is impractically slow - a single small icon was measured at over seven "
        f"minutes without finishing. FSRCNN is sub-second on CPU, but it does not "
        f"produce Real-ESRGAN's invented detail.",
    )


def upscale_image_auto(
    image_path: str,
    scale: int = 4,
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    """Upscale with the best method this machine can actually run."""
    config, manager = _context(config)
    source = resolve_input(image_path, config, "image_path")
    scale = require_positive_int(scale, "scale", maximum=8)

    method, reason = choose_upscale_method(scale, config)
    if method == "fsrcnn" and scale not in images.FSRCNN_SCALES:
        method = "lanczos"
        reason += (
            f" FSRCNN has no x{scale} model (only x2/x3/x4), so Lanczos was used instead."
        )

    logger.info("upscale_image_auto: selected %s (%s)", method, reason)

    if method == "real-esrgan":
        result = upscale_image(str(source), scale, output_path=output_path, overwrite=overwrite, config=config)
    elif method == "fsrcnn":
        result = upscale_image_fast(str(source), scale, output_path=output_path, overwrite=overwrite, config=config)
    else:
        result = _lanczos_upscale(source, scale, manager, output_path, overwrite, config)

    if isinstance(result, str):  # legacy string mode
        return result
    result["operation"] = "upscale_image_auto"
    result["selected_method"] = method
    result["selection_reason"] = reason
    result["quality_note"] = METHOD_NOTES[method]
    result["method_ranking"] = list(QUALITY_ORDER)
    return result


def _lanczos_upscale(source, scale, manager, output_path, overwrite, config):
    with images.open_image(source, config) as opened:
        width, height = opened.size
        images.check_pixel_budget(width * scale, height * scale, source, config)
        enlarged = opened.convert(opened.mode).resize(
            (width * scale, height * scale), Image.LANCZOS
        )
    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("upscaled-lanczos", "png", destination) as staged:
        images.save(enlarged if enlarged.mode != "P" else enlarged.convert("RGBA"), staged.tmp, "PNG")
    return results.build(
        "upscale_image_fast", staged.path, config=config,
        input=str(source), method="lanczos", scale=scale,
        input_width=width, input_height=height,
        actual_width=width * scale, actual_height=height * scale,
    )
