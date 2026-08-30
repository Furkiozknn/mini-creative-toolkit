import logging
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

import httpx
from mcp.server import MCPServer
from PIL import Image

logger = logging.getLogger(__name__)

mcp = MCPServer("mini-creative-toolkit")

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _stamp(prefix: str, ext: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return OUTPUT_DIR / f"{prefix}-{ts}.{ext}"


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-1500:]}")


@mcp.tool()
def generate_image_free(prompt: str, width: int = 1024, height: int = 1024, seed: int | None = None) -> str:
    """Generate an image from a text prompt via Pollinations.ai - genuinely free, no API key or signup required."""
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}"
    params = {"width": width, "height": height, "nologo": "true"}
    if seed is not None:
        params["seed"] = seed

    response = httpx.get(url, params=params, timeout=60.0, follow_redirects=True)
    response.raise_for_status()

    out_path = _stamp("generated", "jpg")
    out_path.write_bytes(response.content)
    logger.info("Generated image for %r -> %s", prompt, out_path)
    return str(out_path)


@mcp.tool()
def remove_background(image_path: str) -> str:
    """Remove the background from an image, saved as a transparent PNG. CPU-only (ONNX via rembg), no API key or GPU needed."""
    from rembg import remove

    src = Path(image_path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {image_path}")

    out_path = _stamp("nobg", "png")
    with open(src, "rb") as f:
        input_bytes = f.read()
    output_bytes = remove(input_bytes)
    out_path.write_bytes(output_bytes)
    logger.info("Background removed: %s -> %s", src, out_path)
    return str(out_path)


@mcp.tool()
def resize_image(image_path: str, width: int, height: int, keep_aspect: bool = True) -> str:
    """Resize an image with high-quality Lanczos resampling. If keep_aspect is true, fits within width x height without distorting."""
    src = Path(image_path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {image_path}")

    img = Image.open(src)
    if keep_aspect:
        img = img.copy()
        img.thumbnail((width, height), Image.LANCZOS)
    else:
        img = img.resize((width, height), Image.LANCZOS)

    out_path = _stamp("resized", src.suffix.lstrip(".") or "png")
    img.save(out_path)
    logger.info("Resized %s to %dx%d (max) -> %s", src, width, height, out_path)
    return str(out_path)


@mcp.tool()
def convert_format(image_path: str, target_format: str) -> str:
    """Convert an image to another format (png, jpg, webp). Flattens transparency onto white when converting to jpg."""
    src = Path(image_path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {image_path}")

    fmt = target_format.lower().lstrip(".")
    if fmt == "jpg":
        fmt = "jpeg"

    img = Image.open(src)
    if fmt == "jpeg" and img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = bg

    ext = "jpg" if fmt == "jpeg" else fmt
    out_path = _stamp("converted", ext)
    img.save(out_path, format=fmt.upper())
    logger.info("Converted %s -> %s", src, out_path)
    return str(out_path)


@mcp.tool()
def video_thumbnail(video_path: str, timestamp: str = "00:00:01") -> str:
    """Grab a single frame from a video as a PNG thumbnail. timestamp is HH:MM:SS."""
    src = Path(video_path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {video_path}")

    out_path = _stamp("thumb", "png")
    _run_ffmpeg(["-ss", timestamp, "-i", str(src), "-frames:v", "1", str(out_path)])
    logger.info("Thumbnail from %s @ %s -> %s", src, timestamp, out_path)
    return str(out_path)


@mcp.tool()
def video_to_gif(video_path: str, start: str = "00:00:00", duration: float = 3.0, fps: int = 12, width: int = 480) -> str:
    """Convert a video clip to an optimized GIF using a two-pass palette for better quality/size."""
    src = Path(video_path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {video_path}")

    palette = _stamp("palette", "png")
    out_path = _stamp("clip", "gif")
    scale = f"fps={fps},scale={width}:-1:flags=lanczos"

    _run_ffmpeg(["-ss", start, "-t", str(duration), "-i", str(src), "-vf", f"{scale},palettegen", str(palette)])
    _run_ffmpeg([
        "-ss", start, "-t", str(duration), "-i", str(src), "-i", str(palette),
        "-lavfi", f"{scale}[x];[x][1:v]paletteuse", str(out_path),
    ])
    palette.unlink(missing_ok=True)
    logger.info("GIF from %s [%s, %ss] -> %s", src, start, duration, out_path)
    return str(out_path)


@mcp.tool()
def video_trim(video_path: str, start: str, duration: float) -> str:
    """Trim a video without re-encoding (fast, lossless cut on keyframe boundaries)."""
    src = Path(video_path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {video_path}")

    out_path = _stamp("trimmed", src.suffix.lstrip(".") or "mp4")
    try:
        _run_ffmpeg(["-ss", start, "-i", str(src), "-t", str(duration), "-c", "copy", str(out_path)])
    except RuntimeError:
        # stream copy can fail to land on a keyframe boundary; re-encode as a fallback
        _run_ffmpeg(["-ss", start, "-i", str(src), "-t", str(duration), str(out_path)])
    logger.info("Trimmed %s [%s, %ss] -> %s", src, start, duration, out_path)
    return str(out_path)


if __name__ == "__main__":
    mcp.run(transport="stdio")
