"""Inline previews: show the client the image a tool just produced.

Every image tool returns a dict whose ``output_path`` names the file it
wrote. An MCP client - and the model behind it - could only see that path,
so checking a resize, a background cut-out or a watermark meant opening a
file on the server's disk, which a remote client usually cannot do. MCP has
image content for this, and a ``resource_link`` for the file itself.

The preview is a **thumbnail**, not the output: at most PREVIEW_MAX_SIDE
pixels on the long side, re-encoded (PNG when the image has transparency,
JPEG otherwise), so a 40-megapixel upscale does not land in the model's
context as 30 MB of base64. The full-size file is what the resource_link
points at. Building the preview never changes the output file, and a file
that cannot be previewed (not an image, unreadable, an AVIF this Pillow
cannot decode) simply gets no preview - the tool's result is never turned
into an error by its preview.

``MCT_INLINE_PREVIEWS=0`` switches previews off.
"""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path

from mcp.types import ImageContent, ResourceLink

from .log import get_logger

logger = get_logger(__name__)

PREVIEW_ENV = "MCT_INLINE_PREVIEWS"
PREVIEW_MAX_SIDE = 512
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif"}
_MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".gif": "image/gif", ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff",
    ".avif": "image/avif",
}


def enabled() -> bool:
    return os.environ.get(PREVIEW_ENV, "1").strip().lower() not in {"0", "false", "no", "off"}


def output_image(result: object) -> Path | None:
    """The image file a tool result points at, if it points at one."""
    if not isinstance(result, dict):
        return None
    raw = result.get("output_path")
    if not isinstance(raw, str):
        return None
    path = Path(raw)
    if path.suffix.lower() not in IMAGE_SUFFIXES or not path.is_file():
        return None
    return path


def thumbnail(path: Path, max_side: int = PREVIEW_MAX_SIDE) -> ImageContent | None:
    """A small re-encoded copy of `path`, or None if it cannot be made."""
    try:
        from PIL import Image

        with Image.open(path) as img:
            img.seek(0)  # first frame of a GIF or animated WebP
            img.thumbnail((max_side, max_side))
            has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
            out = io.BytesIO()
            if has_alpha:
                img.convert("RGBA").save(out, format="PNG", optimize=True)
                mime = "image/png"
            else:
                img.convert("RGB").save(out, format="JPEG", quality=85)
                mime = "image/jpeg"
    except Exception as exc:  # noqa: BLE001 - a preview is never worth failing a tool over
        logger.debug("no preview for %s: %s", path, exc)
        return None
    return ImageContent(type="image", data=base64.b64encode(out.getvalue()).decode("ascii"), mime_type=mime)


def link(path: Path) -> ResourceLink:
    resolved = path.resolve()
    return ResourceLink(
        type="resource_link", uri=resolved.as_uri(), name=resolved.name,
        mime_type=_MIME.get(resolved.suffix.lower()),
    )
