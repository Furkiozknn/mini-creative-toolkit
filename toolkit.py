import logging
import os
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

import httpx
from mcp.server import MCPServer
from PIL import Image, ImageDraw, ImageFont

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


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def _require_positive(**kwargs) -> None:
    for name, value in kwargs.items():
        if value <= 0:
            raise ValueError(f"{name} must be > 0, got {value}")


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


# These hardcoded paths only ever worked on the original dev's Windows machine - they are kept
# purely as a documented fallback default, never assume they resolve on your install. Point
# UPSCAYL_BIN_PATH / UPSCAYL_MODELS_PATH at your own Upscayl checkout to actually use this tool.
UPSCAYL_BIN = Path(
    os.environ.get("UPSCAYL_BIN_PATH")
    or r"C:\Users\furki\Desktop\Claude projeler\upscayl\resources\win\bin\upscayl-bin.exe"
)
UPSCAYL_MODELS = Path(
    os.environ.get("UPSCAYL_MODELS_PATH")
    or r"C:\Users\furki\Desktop\Claude projeler\upscayl\resources\models"
)


@mcp.tool()
def upscale_image(image_path: str, scale: int = 4, model: str = "upscayl-standard-4x") -> str:
    """Upscale an image with real-ESRGAN via Vulkan (reuses Upscayl's bundled binary/models). Tested and confirmed CORRECTLY SLOW to the point of impracticality on Intel integrated graphics (minutes for a single small icon) - only use this if the machine has a real discrete GPU. Otherwise prefer upscale_image_fast (CPU, sub-second, meaningfully better than plain resize) or accept the wait. Requires UPSCAYL_BIN_PATH and UPSCAYL_MODELS_PATH env vars pointing at a local Upscayl install - there is no bundled default that works outside the original dev's machine."""
    src = Path(image_path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {image_path}")
    if not UPSCAYL_BIN.exists():
        raise FileNotFoundError(
            f"Upscayl binary not found at {UPSCAYL_BIN} - set the UPSCAYL_BIN_PATH env var to your "
            "upscayl-bin executable (and UPSCAYL_MODELS_PATH to its models/ dir), or clone/build the "
            "upscayl repo first"
        )
    if not UPSCAYL_MODELS.exists():
        raise FileNotFoundError(
            f"Upscayl models dir not found at {UPSCAYL_MODELS} - set the UPSCAYL_MODELS_PATH env var "
            "to point at Upscayl's resources/models directory"
        )

    out_path = _stamp("upscaled", "png")
    result = subprocess.run(
        [str(UPSCAYL_BIN), "-i", str(src), "-o", str(out_path), "-m", str(UPSCAYL_MODELS), "-n", model, "-s", str(scale)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"upscayl-bin failed: {result.stderr[-1500:]}")
    logger.info("Upscaled %s (%dx, %s) -> %s", src, scale, model, out_path)
    return str(out_path)


FSRCNN_MODELS = {
    2: Path(__file__).parent / "models" / "FSRCNN_x2.pb",
    3: Path(__file__).parent / "models" / "FSRCNN_x3.pb",
    4: Path(__file__).parent / "models" / "FSRCNN_x4.pb",
}


@mcp.tool()
def upscale_image_fast(image_path: str, scale: int = 4) -> str:
    """Upscale an image with FSRCNN, a small pretrained CNN (~40KB, OpenCV's dnn_superres) - runs in well under a second on CPU, no GPU/Vulkan involved. This is the practical default on machines without a discrete GPU: meaningfully sharper edges than plain Lanczos resize, at roughly the speed of resize_image. It is NOT Real-ESRGAN quality (no hallucinated detail/texture) - for that, use upscale_image if you have a discrete GPU and can wait. Supports scale 2, 3, or 4."""
    import cv2

    src = Path(image_path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {image_path}")
    if scale not in FSRCNN_MODELS:
        raise ValueError(f"scale must be one of {sorted(FSRCNN_MODELS)}, got {scale}")

    model_path = FSRCNN_MODELS[scale]
    if not model_path.exists():
        raise FileNotFoundError(f"FSRCNN model not found at {model_path} - expected to ship in the repo's models/ dir")

    img = cv2.imread(str(src))
    if img is None:
        raise ValueError(f"Could not read image (unsupported format or corrupt file): {image_path}")

    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    sr.readModel(str(model_path))
    sr.setModel("fsrcnn", scale)
    result = sr.upsample(img)

    out_path = _stamp("upscaled-fast", "png")
    cv2.imwrite(str(out_path), result)
    logger.info("Fast-upscaled %s (%dx, FSRCNN) -> %s", src, scale, out_path)
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
    _require_positive(width=width, height=height)

    with Image.open(src) as opened:
        if keep_aspect:
            img = opened.copy()
            img.thumbnail((width, height), Image.LANCZOS)
        else:
            img = opened.resize((width, height), Image.LANCZOS)

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

    with Image.open(src) as opened:
        if fmt == "jpeg" and opened.mode in ("RGBA", "LA", "P"):
            rgba = opened.convert("RGBA")
            img = Image.new("RGB", opened.size, (255, 255, 255))
            img.paste(rgba, mask=rgba.split()[-1])
        else:
            img = opened.copy()

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
    _require_positive(duration=duration, fps=fps, width=width)

    palette = _stamp("palette", "png")
    out_path = _stamp("clip", "gif")
    scale = f"fps={fps},scale={width}:-1:flags=lanczos"

    try:
        _run_ffmpeg(["-ss", start, "-t", str(duration), "-i", str(src), "-vf", f"{scale},palettegen", str(palette)])
        _run_ffmpeg([
            "-ss", start, "-t", str(duration), "-i", str(src), "-i", str(palette),
            "-lavfi", f"{scale}[x];[x][1:v]paletteuse", str(out_path),
        ])
    finally:
        palette.unlink(missing_ok=True)
    logger.info("GIF from %s [%s, %ss] -> %s", src, start, duration, out_path)
    return str(out_path)


@mcp.tool()
def video_trim(video_path: str, start: str, duration: float) -> str:
    """Trim a video without re-encoding (fast, lossless cut on keyframe boundaries)."""
    src = Path(video_path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {video_path}")
    _require_positive(duration=duration)

    out_path = _stamp("trimmed", src.suffix.lstrip(".") or "mp4")
    copy_args = ["-ss", start, "-i", str(src), "-t", str(duration), "-c", "copy", str(out_path)]
    reencode_args = ["-ss", start, "-i", str(src), "-t", str(duration), str(out_path)]

    needs_reencode = True
    try:
        _run_ffmpeg(copy_args)
        # -c copy can exit 0 but land off the nearest keyframe instead of erroring,
        # producing a clip noticeably shorter than requested - check the real output.
        needs_reencode = _probe_duration(out_path) < duration * 0.9
    except (RuntimeError, ValueError):
        needs_reencode = True

    if needs_reencode:
        _run_ffmpeg(reencode_args)
    logger.info("Trimmed %s [%s, %ss] -> %s", src, start, duration, out_path)
    return str(out_path)


@mcp.tool()
def strip_metadata(image_path: str) -> str:
    """Strip EXIF/metadata (GPS location, camera model, timestamps, etc.) from an image and save a clean copy. Privacy tool, not a creative one - no model, no network, just rebuilds the image from raw pixel data so nothing but the pixels survives."""
    src = Path(image_path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {image_path}")

    with Image.open(src) as opened:
        # Rebuilding from raw pixel bytes (instead of opened.save with exif=b"") is the
        # reliable way to drop *every* metadata chunk, not only EXIF - ICC profiles, XMP,
        # PNG tEXt chunks, etc. all get left behind too.
        clean = Image.frombytes(opened.mode, opened.size, opened.tobytes())

    out_path = _stamp("stripped", src.suffix.lstrip(".") or "png")
    clean.save(out_path)
    logger.info("Stripped metadata: %s -> %s", src, out_path)
    return str(out_path)


_WATERMARK_POSITIONS = {"top-left", "top-right", "bottom-left", "bottom-right", "center"}


@mcp.tool()
def add_watermark(
    image_path: str,
    text: str,
    position: str = "bottom-right",
    opacity: float = 0.5,
    font_size: int = 24,
) -> str:
    """Overlay semi-transparent text onto an image - a watermark/caption, not a filter. position is one of top-left, top-right, bottom-left, bottom-right, center. opacity is 0 (invisible) to 1 (solid). Pillow only, no model."""
    src = Path(image_path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {image_path}")
    if position not in _WATERMARK_POSITIONS:
        raise ValueError(f"position must be one of {sorted(_WATERMARK_POSITIONS)}, got {position!r}")
    if not 0.0 <= opacity <= 1.0:
        raise ValueError(f"opacity must be between 0 and 1, got {opacity}")
    _require_positive(font_size=font_size)

    with Image.open(src) as opened:
        original_mode = opened.mode
        base = opened.convert("RGBA")

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default(size=font_size)

    margin = max(font_size // 4, 4)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = right - left, bottom - top

    x_positions = {"top-left": margin, "bottom-left": margin, "center": (base.width - text_w) // 2}
    x_positions["top-right"] = base.width - text_w - margin
    x_positions["bottom-right"] = base.width - text_w - margin
    y_positions = {"top-left": margin, "top-right": margin, "center": (base.height - text_h) // 2}
    y_positions["bottom-left"] = base.height - text_h - margin
    y_positions["bottom-right"] = base.height - text_h - margin

    xy = (x_positions[position] - left, y_positions[position] - top)
    draw.text(xy, text, font=font, fill=(255, 255, 255, round(255 * opacity)))

    composited = Image.alpha_composite(base, overlay)

    ext = src.suffix.lstrip(".") or "png"
    if ext.lower() in ("jpg", "jpeg") or original_mode not in ("RGBA", "LA"):
        # Flatten onto white so formats without alpha (or images that started opaque) save cleanly.
        flattened = Image.new("RGB", composited.size, (255, 255, 255))
        flattened.paste(composited, mask=composited.split()[-1])
        result = flattened
    else:
        result = composited

    out_path = _stamp("watermarked", ext)
    result.save(out_path)
    logger.info("Watermarked %s with %r @ %s -> %s", src, text, position, out_path)
    return str(out_path)


@mcp.tool()
def extract_audio(video_path: str, audio_format: str = "mp3") -> str:
    """Pull the audio track out of a video file via ffmpeg, saved as mp3 or wav. No video re-encode, no model - straight audio extraction."""
    src = Path(video_path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {video_path}")

    fmt = audio_format.lower().lstrip(".")
    if fmt not in ("mp3", "wav"):
        raise ValueError(f"audio_format must be 'mp3' or 'wav', got {audio_format!r}")

    out_path = _stamp("audio", fmt)
    codec_args = ["-acodec", "libmp3lame", "-q:a", "2"] if fmt == "mp3" else ["-acodec", "pcm_s16le"]
    _run_ffmpeg(["-i", str(src), "-vn", *codec_args, str(out_path)])
    logger.info("Extracted %s audio from %s -> %s", fmt, src, out_path)
    return str(out_path)


if __name__ == "__main__":
    mcp.run(transport="stdio")
