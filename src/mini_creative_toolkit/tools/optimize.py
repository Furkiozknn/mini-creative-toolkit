"""``optimize_media`` - inspect first, then decide, then say what changed.

The rule this tool follows: never silently degrade quality. Every lossy step
is named in ``quality_notes``, and when the "optimised" file comes out larger
than the original that is reported as a fact rather than hidden behind a
percentage that happens to be positive.
"""

from __future__ import annotations

from pathlib import Path

from .. import results
from ..config import Config, get_config
from ..engines import images
from ..errors import InvalidInputError
from ..log import get_logger
from ..media_info import describe
from ..paths import OutputManager, resolve_input
from ..validation import require_choice, require_positive_int
from . import presets as preset_module
from .video import video_compress

logger = get_logger(__name__)

GOALS = {"web", "quality", "smallest", "social", "archive"}

#: (format preference order, quality, note) per goal for images.
_IMAGE_PLAN = {
    "web": (("WEBP", "JPEG", "PNG"), 82, "Tuned for download size at a quality most viewers cannot distinguish."),
    "social": (("JPEG", "WEBP", "PNG"), 88, "Higher quality than 'web' because social platforms re-encode uploads."),
    "smallest": (("WEBP", "JPEG"), 65, "Aggressively small. Visible artefacts are likely on detailed images."),
    "quality": (("PNG", "WEBP"), 95, "Prefers lossless; falls back to high-quality lossy only if lossless is unavailable."),
    "archive": (("PNG",), None, "Lossless PNG. Pixel data is preserved exactly."),
}


def optimize_media(
    path: str,
    goal: str = "web",
    max_width: int | None = None,
    max_height: int | None = None,
    preset: str | None = None,
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    config = config or get_config()
    manager = OutputManager(config)
    source = resolve_input(path, config, "path")
    goal = require_choice(goal, "goal", GOALS)

    info = describe(source, config)
    if info["kind"] == "image":
        return _optimize_image(
            source, info, goal, max_width, max_height, preset, output_path, overwrite, config, manager
        )
    if info["kind"] == "video":
        return _optimize_video(source, info, goal, output_path, overwrite, config)
    raise InvalidInputError(
        f"optimize_media handles images and video. {source.name} is audio - use "
        f"extract_audio or convert it with ffmpeg directly."
    )


def _optimize_image(source, info, goal, max_width, max_height, preset, output_path, overwrite, config, manager):
    order, quality, goal_note = _IMAGE_PLAN[goal]
    operations: list[str] = []
    quality_notes = [goal_note]

    if preset is not None:
        max_width, max_height = preset_module.resolve("image", preset)
        operations.append(f"preset '{preset}' -> fit within {max_width}x{max_height}")
        quality_notes.append(preset_module.DISCLAIMER)
    if max_width is not None:
        max_width = require_positive_int(max_width, "max_width", maximum=100_000)
    if max_height is not None:
        max_height = require_positive_int(max_height, "max_height", maximum=100_000)

    has_alpha = info["has_alpha"]
    chosen = _choose_image_format(order, has_alpha, goal)
    if has_alpha and chosen == "JPEG":
        # Only reachable if neither WEBP nor PNG is writable in this build.
        quality_notes.append("Transparency was flattened onto white because JPEG has no alpha channel.")

    with images.open_image(source, config) as opened:
        img = opened.copy()
        original_size = img.size
        target = original_size
        if max_width or max_height:
            target = images.fit_within(
                original_size, max_width or original_size[0], max_height or original_size[1]
            )
            if target != original_size:
                img = img.resize(target, images.Image.LANCZOS)
                operations.append(f"resize {original_size[0]}x{original_size[1]} -> {target[0]}x{target[1]}")
        if chosen == "JPEG" and images.has_alpha(img):
            img = images.flatten_onto(img, (255, 255, 255))
            operations.append("flatten alpha onto white")
        elif img.mode == "P":
            img = img.convert("RGBA" if images.has_alpha(img) else "RGB")

    if chosen != info["format"]:
        operations.append(f"re-encode {info['format']} -> {chosen}")
    else:
        operations.append(f"re-encode {chosen} (recompress)")
    if chosen in ("JPEG", "WEBP") and quality is not None:
        quality_notes.append(
            f"Lossy re-encode at quality {quality}. The original pixel data is not recoverable "
            f"from the output; keep the source file."
        )

    ext = images.EXTENSION_FOR[chosen]
    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("optimized", ext, destination) as staged:
        images.save(img, staged.tmp, chosen, quality=quality)

    input_size = source.stat().st_size
    output_size = staged.path.stat().st_size
    change = results.percent_change(input_size, output_size)
    if output_size >= input_size:
        quality_notes.append(
            f"The optimised file is not smaller ({output_size:,} vs {input_size:,} bytes). "
            f"The source was already well compressed for this goal - keep the original."
        )

    return results.build(
        "optimize_media", staged.path, config=config,
        input=str(source), kind="image", goal=goal,
        operations=operations,
        input_size=input_size, output_size=output_size, size_change_percent=change,
        format=chosen, quality=quality,
        actual_width=img.size[0], actual_height=img.size[1],
        quality_notes=quality_notes,
    )


def _choose_image_format(order, has_alpha: bool, goal: str) -> str:
    available = {images.FORMAT_ALIASES[name] for name in images.writable_formats()}
    for fmt in order:
        if fmt not in available:
            continue
        if has_alpha and fmt == "JPEG" and goal != "smallest":
            # Losing transparency is a change of content, not of quality.
            # Only 'smallest' is allowed to make that trade, and it says so.
            continue
        return fmt
    return "PNG"


_VIDEO_CRF = {"web": 26, "social": 24, "smallest": 32, "quality": 20, "archive": 18}


def _optimize_video(source: Path, info: dict, goal: str, output_path, overwrite, config):
    crf = _VIDEO_CRF[goal]
    result = video_compress(
        str(source), crf=crf, preset="medium",
        output_path=output_path, overwrite=overwrite, config=config,
    )
    if isinstance(result, str):
        return result
    output_size = result.get("output_size_bytes", 0)
    input_size = info["file_size_bytes"]
    result.update(
        {
            "operation": "optimize_media",
            "kind": "video",
            "goal": goal,
            "operations": [
                f"inspect: {info.get('video_codec')} in {info.get('container')}",
                f"re-encode to H.264/AAC at CRF {crf} for goal '{goal}'",
            ],
            "input_size": input_size,
            "output_size": output_size,
            "size_change_percent": results.percent_change(input_size, output_size),
        }
    )
    return result
