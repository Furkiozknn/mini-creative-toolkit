"""Structured description of a media file. Pillow for images, ffprobe for AV.

``inspect_media`` is the tool this powers, but it is also the first step of
``optimize_media`` - the whole point of that tool is to decide from the real
properties of a file rather than from its extension.
"""

from __future__ import annotations

from math import gcd
from pathlib import Path

from .config import Config, get_config
from .engines import ffmpeg
from .engines.images import header_size, open_image
from .errors import ExternalToolError, InvalidInputError

#: Extensions ffprobe should handle. Anything else is tried as an image first.
_AV_SUFFIXES = {
    ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".flv", ".wmv", ".mpg", ".mpeg", ".ts", ".m2ts",
    ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".oga", ".opus", ".wma", ".aiff",
}


def aspect_ratio(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "unknown"
    divisor = gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def classify(path: Path) -> str:
    """"image", "video", "audio" - decided by content, not just by name."""
    suffix = path.suffix.lower()
    if suffix not in _AV_SUFFIXES:
        try:
            header_size(path)
            return "image"
        except InvalidInputError:
            pass
    if not ffmpeg.available("ffprobe"):
        raise InvalidInputError(
            f"{path.name} is not an image Pillow can read, and ffprobe is not "
            f"installed to identify it as audio or video."
        )
    try:
        info = ffmpeg.probe(path)
    except ExternalToolError as exc:
        # Neither Pillow nor ffprobe can make sense of the file. From the
        # caller's side that is bad input, not a tool malfunction - and the
        # distinction matters, because a batch reports the two differently.
        raise InvalidInputError(
            f"{path.name} is not a media file this toolkit can read - neither Pillow "
            f"nor ffprobe recognises it.",
            detail=exc.detail,
        ) from None
    grouped = ffmpeg.streams_by_type(info)
    if grouped.get("video"):
        # A single-frame "video" stream is how ffprobe reports a still image
        # inside a container it understands (and cover art inside an mp3).
        if not grouped.get("audio") and _looks_like_still(grouped["video"][0]):
            return "image"
        return "video"
    if grouped.get("audio"):
        return "audio"
    raise InvalidInputError(f"{path.name} contains no audio or video streams.")


def _looks_like_still(stream: dict) -> bool:
    return stream.get("codec_name") in {"png", "mjpeg", "bmp", "gif", "webp"} and (
        stream.get("nb_frames") in (None, "1", 1)
    )


def describe(raw_path: Path, config: Config | None = None) -> dict:
    config = config or get_config()
    kind = classify(raw_path)
    if kind == "image":
        return _describe_image(raw_path, config)
    return _describe_av(raw_path, kind, config)


def _describe_image(path: Path, config: Config) -> dict:
    stat = path.stat()
    width, height, fmt = header_size(path)
    with open_image(path, config) as img:
        info = dict(img.info)
        frames = getattr(img, "n_frames", 1)
        mode = img.mode
        exif = img.getexif()
        has_exif = bool(exif) and len(exif) > 0
    metadata_keys = sorted(k for k in info if k not in ("icc_profile", "exif"))
    return {
        "path": str(path),
        "kind": "image",
        "format": fmt,
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio(width, height),
        "color_mode": mode,
        "has_alpha": mode in ("RGBA", "LA", "PA") or "transparency" in info,
        "file_size_bytes": stat.st_size,
        "frame_count": int(frames or 1),
        "animated": bool(frames and frames > 1),
        "has_exif": has_exif,
        "has_icc_profile": "icc_profile" in info,
        "metadata_keys": metadata_keys,
        "has_metadata": bool(has_exif or "icc_profile" in info or metadata_keys),
    }


def _describe_av(path: Path, kind: str, config: Config) -> dict:
    stat = path.stat()
    info = ffmpeg.probe(path, config)
    fmt = info.get("format", {})
    grouped = ffmpeg.streams_by_type(info)
    video = (grouped.get("video") or [None])[0]
    audio = (grouped.get("audio") or [None])[0]

    duration = None
    raw_duration = fmt.get("duration")
    if raw_duration is not None:
        try:
            duration = round(float(raw_duration), 3)
        except (TypeError, ValueError):
            duration = None

    result = {
        "path": str(path),
        "kind": kind,
        "container": fmt.get("format_name"),
        "container_long": fmt.get("format_long_name"),
        "duration_seconds": duration,
        "file_size_bytes": stat.st_size,
        "bitrate": _int_or_none(fmt.get("bit_rate")),
        "has_audio": audio is not None,
        "has_video": video is not None,
        "metadata_keys": sorted(fmt.get("tags", {})),
        "has_metadata": bool(fmt.get("tags")),
    }

    if video is not None:
        width = _int_or_none(video.get("width")) or 0
        height = _int_or_none(video.get("height")) or 0
        result.update(
            {
                "width": width,
                "height": height,
                "aspect_ratio": aspect_ratio(width, height),
                "video_codec": video.get("codec_name"),
                "pixel_format": video.get("pix_fmt"),
                "fps": _round_or_none(ffmpeg.parse_fraction(video.get("avg_frame_rate"))),
                "frame_count": _int_or_none(video.get("nb_frames")),
                "video_bitrate": _int_or_none(video.get("bit_rate")),
            }
        )
    if audio is not None:
        result.update(
            {
                "audio_codec": audio.get("codec_name"),
                "sample_rate": _int_or_none(audio.get("sample_rate")),
                "channels": _int_or_none(audio.get("channels")),
                "channel_layout": audio.get("channel_layout"),
                "audio_bitrate": _int_or_none(audio.get("bit_rate")),
            }
        )
    return result


def _int_or_none(raw: object) -> int | None:
    try:
        return int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _round_or_none(raw: float | None) -> float | None:
    return round(raw, 3) if raw is not None else None
