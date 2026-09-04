"""Pillow and OpenCV: opening, encoding, and super-resolution.

The one non-obvious thing here is the decompression-bomb guard. Pillow ships
one (``Image.MAX_IMAGE_PIXELS``) but it raises a *warning* by default, not an
error, and it is a process-global. Since this server accepts image paths from
an MCP client, a 60000x60000 PNG that decompresses to gigabytes is a real
denial-of-service input, so the size is checked from the header before any
pixel data is decoded.
"""

from __future__ import annotations

import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from PIL import Image, UnidentifiedImageError

from ..config import Config, get_config
from ..errors import (
    InvalidInputError,
    MissingDependencyError,
    ModelUnavailableError,
    ResourceLimitError,
    UnsupportedFormatError,
)
from ..log import get_logger

logger = get_logger(__name__)

#: Pillow's own bomb warning would otherwise fire before ours and be swallowed.
Image.MAX_IMAGE_PIXELS = None

#: Canonical names -> Pillow's format identifiers.
FORMAT_ALIASES = {
    "png": "PNG",
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
    "avif": "AVIF",
    "tif": "TIFF",
    "tiff": "TIFF",
    "bmp": "BMP",
    "gif": "GIF",
}

#: Formats this tool will *write*. Reading is broader - Pillow reads plenty
#: of things nobody should be asked to write.
WRITABLE = ("png", "jpeg", "webp", "avif")

#: Extension used on disk for each Pillow format.
EXTENSION_FOR = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp", "AVIF": "avif", "TIFF": "tiff", "BMP": "bmp", "GIF": "gif"}

_LOSSY = {"JPEG", "WEBP", "AVIF"}


def canonical_format(raw: str) -> str:
    key = raw.strip().lower().lstrip(".")
    if key not in FORMAT_ALIASES:
        raise UnsupportedFormatError(
            f"Unknown image format {raw!r}. Known names: {', '.join(sorted(FORMAT_ALIASES))}"
        )
    return FORMAT_ALIASES[key]


def writable_formats() -> list[str]:
    """Which of :data:`WRITABLE` this Pillow build can actually encode."""
    Image.init()
    available = []
    for name in WRITABLE:
        fmt = FORMAT_ALIASES[name]
        if fmt in Image.SAVE:
            available.append(name)
    return available


def require_writable(fmt: str) -> str:
    Image.init()
    if fmt not in Image.SAVE:
        raise UnsupportedFormatError(
            f"This Pillow installation cannot write {fmt}. Available: "
            f"{', '.join(writable_formats())}. (AVIF in particular depends on how "
            f"Pillow was built - it is not always present.)"
        )
    return fmt


def header_size(path: Path) -> tuple[int, int, str]:
    """Read dimensions and format from the header without decoding pixels."""
    try:
        with Image.open(path) as img:
            return img.width, img.height, (img.format or "unknown")
    except UnidentifiedImageError:
        raise InvalidInputError(
            f"{path.name} is not an image file Pillow recognises."
        ) from None
    except (OSError, ValueError) as exc:
        raise InvalidInputError(f"Could not read {path.name} as an image: {exc}") from None


def check_pixel_budget(width: int, height: int, path: Path, config: Config | None = None) -> None:
    config = config or get_config()
    pixels = width * height
    if pixels > config.max_image_pixels:
        raise ResourceLimitError(
            f"{path.name} is {width}x{height} = {pixels:,} pixels, above the "
            f"{config.max_image_pixels:,} pixel limit. Decoding it would allocate "
            f"roughly {pixels * 4 / 1024 / 1024:.0f} MB. Raise MCT_MAX_IMAGE_PIXELS "
            f"if this file is legitimate.",
            limit_name="MCT_MAX_IMAGE_PIXELS",
            limit_value=config.max_image_pixels,
            actual=pixels,
        )


@contextmanager
def open_image(path: Path, config: Config | None = None) -> Iterator[Image.Image]:
    """Open an image after checking its declared size against the budget."""
    config = config or get_config()
    width, height, _ = header_size(path)
    check_pixel_budget(width, height, path, config)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as img:
                img.load()
                yield img
    except Image.DecompressionBombError as exc:  # pragma: no cover - guarded above
        raise ResourceLimitError(
            str(exc), limit_name="MCT_MAX_IMAGE_PIXELS", limit_value=config.max_image_pixels
        ) from None
    except UnidentifiedImageError:
        raise InvalidInputError(f"{path.name} is not an image file Pillow recognises.") from None
    except OSError as exc:
        raise InvalidInputError(f"Could not decode {path.name}: {exc}") from None


def flatten_onto(img: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    """Composite an image with alpha onto an opaque background."""
    rgba = img.convert("RGBA")
    flat = Image.new("RGB", rgba.size, background)
    flat.paste(rgba, mask=rgba.split()[-1])
    return flat


def has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info


def save(
    img: Image.Image,
    destination: Path,
    fmt: str,
    quality: int | None = None,
    lossless: bool = False,
) -> None:
    """Encode to ``destination`` with format-appropriate options."""
    require_writable(fmt)
    options: dict = {}
    if fmt in _LOSSY:
        if lossless and fmt in ("WEBP", "AVIF"):
            options["lossless"] = True
        elif quality is not None:
            options["quality"] = int(quality)
        if fmt == "JPEG":
            options.setdefault("quality", 90)
            options["optimize"] = True
            options["progressive"] = True
    elif fmt == "PNG":
        options["optimize"] = True
    # Never carry EXIF/ICC through implicitly: a caller who asked for a
    # resize did not ask to have GPS coordinates copied into the new file.
    # `strip_metadata` and `inspect_media` make metadata handling explicit.
    try:
        img.save(destination, format=fmt, **options)
    except (OSError, ValueError, KeyError) as exc:
        raise UnsupportedFormatError(
            f"Pillow could not write {fmt}: {exc}", detail=repr(exc)
        ) from None


def fit_within(size: tuple[int, int], width: int, height: int) -> tuple[int, int]:
    """Largest ``(w, h)`` inside ``width x height`` with the original ratio."""
    src_w, src_h = size
    if src_w <= 0 or src_h <= 0:
        raise InvalidInputError(f"Source image has a degenerate size {size}")
    scale = min(width / src_w, height / src_h)
    return max(1, round(src_w * scale)), max(1, round(src_h * scale))


# --- OpenCV / FSRCNN ---------------------------------------------------------

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
FSRCNN_SCALES = (2, 3, 4)


def fsrcnn_model_path(scale: int) -> Path:
    path = MODEL_DIR / f"FSRCNN_x{scale}.pb"
    if not path.is_file():
        raise ModelUnavailableError(
            f"FSRCNN weights for scale {scale} are missing at {path}. They ship inside "
            f"the package; a partial install or a stripped wheel would explain this."
        )
    return path


def fsrcnn_upscale(source: Path, destination: Path, scale: int) -> tuple[int, int]:
    """Run FSRCNN super-resolution. Returns the output dimensions."""
    try:
        import cv2
    except ImportError:  # pragma: no cover - opencv is a hard dependency
        raise MissingDependencyError(
            "opencv-contrib-python is not installed, so FSRCNN upscaling is unavailable."
        ) from None
    if not hasattr(cv2, "dnn_superres"):
        raise MissingDependencyError(
            "This OpenCV build has no dnn_superres module. Install "
            "'opencv-contrib-python' rather than plain 'opencv-python'."
        )
    model = fsrcnn_model_path(scale)
    image = cv2.imread(str(source))
    if image is None:
        raise InvalidInputError(
            f"OpenCV could not decode {source.name}. Convert it to PNG or JPEG first."
        )
    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    sr.readModel(str(model))
    sr.setModel("fsrcnn", scale)
    result = sr.upsample(image)
    if not cv2.imwrite(str(destination), result):
        raise UnsupportedFormatError(f"OpenCV could not write {destination.suffix} output")
    return int(result.shape[1]), int(result.shape[0])
