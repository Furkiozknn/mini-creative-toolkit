"""Image operations: resize, convert, strip metadata, watermark, sheets, compare."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .. import results
from ..config import Config, get_config
from ..engines import images
from ..errors import InvalidInputError
from ..log import get_logger
from ..paths import OutputManager, resolve_input, resolve_input_list
from ..validation import (
    require_choice,
    require_positive_int,
    require_ratio,
    require_text,
)

logger = get_logger(__name__)

WATERMARK_POSITIONS = {"top-left", "top-right", "bottom-left", "bottom-right", "center"}


def _context(config: Config | None = None) -> tuple[Config, OutputManager]:
    config = config or get_config()
    return config, OutputManager(config)


def resize_image(
    image_path: str,
    width: int,
    height: int,
    keep_aspect: bool = True,
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    config, manager = _context(config)
    source = resolve_input(image_path, config, "image_path")
    width = require_positive_int(width, "width", maximum=100_000)
    height = require_positive_int(height, "height", maximum=100_000)

    with images.open_image(source, config) as opened:
        original_size = opened.size
        if keep_aspect:
            target = images.fit_within(original_size, width, height)
        else:
            target = (width, height)
        resized = opened.convert(opened.mode).resize(target, Image.LANCZOS)
        fmt = images.canonical_format(source.suffix or "png")
        if fmt not in ("PNG", "JPEG", "WEBP", "AVIF"):
            fmt = "PNG"
        if fmt == "JPEG" and images.has_alpha(resized):
            resized = images.flatten_onto(resized, (255, 255, 255))
        ext = images.EXTENSION_FOR[fmt]

    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("resized", ext, destination) as staged:
        images.save(resized, staged.tmp, fmt)

    logger.info("resize_image: %s %s -> %s", source.name, original_size, target)
    return results.build(
        "resize_image",
        staged.path,
        config=config,
        input=str(source),
        requested_width=width,
        requested_height=height,
        actual_width=target[0],
        actual_height=target[1],
        keep_aspect=keep_aspect,
        format=fmt,
    )


def convert_format(
    image_path: str,
    target_format: str,
    quality: int | None = None,
    lossless: bool = False,
    background: str = "white",
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    config, manager = _context(config)
    source = resolve_input(image_path, config, "image_path")
    fmt = images.require_writable(images.canonical_format(target_format))
    if quality is not None:
        quality = require_positive_int(quality, "quality", maximum=100)
    rgb_background = _parse_background(background)

    notes: list[str] = []
    with images.open_image(source, config) as opened:
        source_format = opened.format
        img = opened.copy()
        if fmt in ("JPEG",) and images.has_alpha(img):
            img = images.flatten_onto(img, rgb_background)
            notes.append(
                f"JPEG has no alpha channel, so transparency was flattened onto {background}."
            )
        elif fmt == "JPEG" and img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        elif fmt in ("PNG", "WEBP", "AVIF") and img.mode == "P":
            img = img.convert("RGBA" if images.has_alpha(img) else "RGB")

    ext = images.EXTENSION_FOR[fmt]
    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("converted", ext, destination) as staged:
        images.save(img, staged.tmp, fmt, quality=quality, lossless=lossless)

    input_size = source.stat().st_size
    output_size = staged.path.stat().st_size
    return results.build(
        "convert_format",
        staged.path,
        config=config,
        input=str(source),
        source_format=source_format,
        format=fmt,
        quality=quality,
        lossless=bool(lossless and fmt in ("WEBP", "AVIF")),
        input_size_bytes=input_size,
        size_change_percent=results.percent_change(input_size, output_size),
        notes=notes,
    )


_NAMED_COLORS = {
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "grey": (128, 128, 128),
    "gray": (128, 128, 128),
    "transparent": (255, 255, 255),
}


def _parse_background(raw: object) -> tuple[int, int, int]:
    """Accept a named colour or ``#rrggbb``. Nothing else - this reaches a
    drawing call, and accepting arbitrary Pillow colour strings would widen
    the parser surface for no real benefit."""
    if not isinstance(raw, str):
        raise InvalidInputError(f"background must be a string, got {type(raw).__name__}")
    value = raw.strip().lower()
    if value in _NAMED_COLORS:
        return _NAMED_COLORS[value]
    if len(value) == 7 and value.startswith("#"):
        try:
            return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
        except ValueError:
            pass
    raise InvalidInputError(
        f"background must be one of {sorted(_NAMED_COLORS)} or a #rrggbb hex colour, got {raw!r}"
    )


def strip_metadata(
    image_path: str,
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    config, manager = _context(config)
    source = resolve_input(image_path, config, "image_path")

    with images.open_image(source, config) as opened:
        had_exif = bool(opened.getexif())
        had_icc = "icc_profile" in opened.info
        other_keys = sorted(k for k in opened.info if k not in ("icc_profile", "exif"))
        fmt = images.canonical_format(source.suffix or "png")
        if fmt not in ("PNG", "JPEG", "WEBP", "AVIF"):
            fmt = "PNG"
        # Rebuilding from raw pixel bytes drops *every* ancillary chunk, not
        # only EXIF: ICC profiles, XMP, PNG tEXt, all of it. Saving with
        # exif=b"" would leave the rest behind.
        clean = Image.frombytes(opened.mode, opened.size, opened.tobytes())
        if fmt == "JPEG" and clean.mode not in ("RGB", "L"):
            clean = images.flatten_onto(clean, (255, 255, 255))

    ext = images.EXTENSION_FOR[fmt]
    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("stripped", ext, destination) as staged:
        images.save(clean, staged.tmp, fmt)

    return results.build(
        "strip_metadata",
        staged.path,
        config=config,
        input=str(source),
        removed_exif=had_exif,
        removed_icc_profile=had_icc,
        removed_other_keys=other_keys,
        format=fmt,
    )


def add_watermark(
    image_path: str,
    text: str,
    position: str = "bottom-right",
    opacity: float = 0.5,
    font_size: int = 24,
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    config, manager = _context(config)
    source = resolve_input(image_path, config, "image_path")
    text = require_text(text, "text", max_length=200)
    position = require_choice(position, "position", WATERMARK_POSITIONS)
    opacity = require_ratio(opacity, "opacity")
    font_size = require_positive_int(font_size, "font_size", maximum=2000)

    with images.open_image(source, config) as opened:
        original_mode = opened.mode
        base = opened.convert("RGBA")
        fmt = images.canonical_format(source.suffix or "png")
    if fmt not in ("PNG", "JPEG", "WEBP", "AVIF"):
        fmt = "PNG"

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default(size=font_size)
    margin = max(font_size // 4, 4)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = right - left, bottom - top

    x = {
        "top-left": margin,
        "bottom-left": margin,
        "top-right": base.width - text_w - margin,
        "bottom-right": base.width - text_w - margin,
        "center": (base.width - text_w) // 2,
    }[position]
    y = {
        "top-left": margin,
        "top-right": margin,
        "bottom-left": base.height - text_h - margin,
        "bottom-right": base.height - text_h - margin,
        "center": (base.height - text_h) // 2,
    }[position]

    draw.text((x - left, y - top), text, font=font, fill=(255, 255, 255, round(255 * opacity)))
    composited = Image.alpha_composite(base, overlay)

    if fmt == "JPEG" or original_mode not in ("RGBA", "LA", "PA"):
        result_img = images.flatten_onto(composited, (255, 255, 255))
    else:
        result_img = composited

    ext = images.EXTENSION_FOR[fmt]
    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("watermarked", ext, destination) as staged:
        images.save(result_img, staged.tmp, fmt)

    return results.build(
        "add_watermark",
        staged.path,
        config=config,
        input=str(source),
        position=position,
        opacity=opacity,
        font_size=font_size,
        width=base.width,
        height=base.height,
        format=fmt,
    )


def create_contact_sheet(
    image_paths: list[str],
    thumbnail_size: int = 240,
    columns: int = 4,
    padding: int = 12,
    labels: bool = True,
    background: str = "white",
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    """Tile images into one review sheet."""
    config, manager = _context(config)
    sources = resolve_input_list(image_paths, config, "image_paths")
    thumbnail_size = require_positive_int(thumbnail_size, "thumbnail_size", maximum=2000)
    columns = require_positive_int(columns, "columns", maximum=20)
    if not isinstance(padding, int) or isinstance(padding, bool) or padding < 0 or padding > 200:
        raise InvalidInputError(f"padding must be an integer between 0 and 200, got {padding!r}")
    rgb_background = _parse_background(background)

    label_height = max(14, thumbnail_size // 12) if labels else 0
    font = ImageFont.load_default(size=max(9, label_height - 4)) if labels else None

    thumbs: list[tuple[Image.Image, str]] = []
    skipped: list[dict] = []
    for source in sources:
        try:
            with images.open_image(source, config) as opened:
                thumb = opened.convert("RGB").copy()
                thumb.thumbnail((thumbnail_size, thumbnail_size), Image.LANCZOS)
            thumbs.append((thumb, source.name))
        except Exception as exc:  # one unreadable file must not lose the sheet
            skipped.append({"path": str(source), "error": _short_error(exc)})

    if not thumbs:
        raise InvalidInputError(
            "None of the supplied images could be read, so there is nothing to tile."
        )

    rows = (len(thumbs) + columns - 1) // columns
    cell_w = thumbnail_size + padding
    cell_h = thumbnail_size + padding + label_height
    sheet = Image.new(
        "RGB", (columns * cell_w + padding, rows * cell_h + padding), rgb_background
    )
    draw = ImageDraw.Draw(sheet)

    for index, (thumb, name) in enumerate(thumbs):
        col, row = index % columns, index // columns
        cx = padding + col * cell_w + (thumbnail_size - thumb.width) // 2
        cy = padding + row * cell_h + (thumbnail_size - thumb.height) // 2
        sheet.paste(thumb, (cx, cy))
        if labels and font is not None:
            label = name if len(name) <= 28 else name[:13] + "..." + name[-12:]
            draw.text(
                (padding + col * cell_w, padding + row * cell_h + thumbnail_size + 2),
                label,
                font=font,
                fill=(60, 60, 60),
            )

    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("contact-sheet", "png", destination) as staged:
        images.save(sheet, staged.tmp, "PNG")

    return results.build(
        "create_contact_sheet",
        staged.path,
        config=config,
        tiled=len(thumbs),
        skipped=skipped,
        columns=columns,
        rows=rows,
        thumbnail_size=thumbnail_size,
        width=sheet.width,
        height=sheet.height,
    )


def compare_images(image_a: str, image_b: str, config: Config | None = None) -> dict:
    """Compare two images. Deliberately not a forensic identity claim.

    ``identical_bytes`` is exact and trustworthy. ``mean_pixel_difference``
    is a plain average absolute channel difference after resizing both to a
    common small size - useful for "is this the same picture", useless as
    evidence of anything.
    """
    config, _ = _context(config)
    first = resolve_input(image_a, config, "image_a")
    second = resolve_input(image_b, config, "image_b")

    digest_a = _sha256(first)
    digest_b = _sha256(second)
    identical = digest_a == digest_b

    with images.open_image(first, config) as a, images.open_image(second, config) as b:
        size_a, size_b = a.size, b.size
        format_a, format_b = a.format, b.format
        small_a = a.convert("RGB").resize((64, 64), Image.LANCZOS)
        small_b = b.convert("RGB").resize((64, 64), Image.LANCZOS)

    pixels_a = small_a.tobytes()
    pixels_b = small_b.tobytes()
    difference = sum(abs(x - y) for x, y in zip(pixels_a, pixels_b)) / len(pixels_a)

    return {
        "operation": "compare_images",
        "execution": "local",
        "network": "none",
        "image_a": {"path": str(first), "size": list(size_a), "format": format_a,
                     "file_size_bytes": first.stat().st_size, "sha256": digest_a},
        "image_b": {"path": str(second), "size": list(size_b), "format": format_b,
                     "file_size_bytes": second.stat().st_size, "sha256": digest_b},
        "identical_bytes": identical,
        "same_dimensions": size_a == size_b,
        "mean_pixel_difference": round(difference, 4),
        "interpretation": _interpret_difference(identical, difference),
        "caveat": (
            "mean_pixel_difference is a coarse similarity score computed on 64x64 "
            "thumbnails. It is not perceptual hashing and is not forensic evidence "
            "of identity or provenance."
        ),
    }


def _interpret_difference(identical: bool, difference: float) -> str:
    if identical:
        return "byte-identical files"
    if difference < 1.0:
        return "visually near-identical at thumbnail scale (re-encode or metadata change is likely)"
    if difference < 8.0:
        return "similar - probably the same image with edits or different compression"
    return "clearly different images"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _short_error(exc: BaseException) -> str:
    from ..errors import ToolkitError

    if isinstance(exc, ToolkitError):
        return exc.message
    return f"{type(exc).__name__}: {exc}"
