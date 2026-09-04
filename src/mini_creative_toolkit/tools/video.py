"""Video and audio operations, all of them ffmpeg behind the engine wrapper."""

from __future__ import annotations

from pathlib import Path

from .. import results
from ..config import Config, get_config
from ..engines import ffmpeg
from ..errors import ExternalToolError, InvalidInputError, ResourceLimitError
from ..log import get_logger
from ..media_info import describe
from ..paths import OutputManager, resolve_input, scratch_file
from ..validation import (
    require_choice,
    require_positive_int,
    require_positive_number,
    require_timestamp,
)

logger = get_logger(__name__)

AUDIO_FORMATS = {"mp3", "wav"}
VIDEO_CONTAINERS = {"mp4", "mkv", "webm", "mov"}


def _context(config: Config | None = None) -> tuple[Config, OutputManager]:
    config = config or get_config()
    return config, OutputManager(config)


def _check_video_limits(info: dict, config: Config, path: Path) -> None:
    duration = info.get("duration_seconds")
    if duration is not None and duration > config.max_video_duration_seconds:
        raise ResourceLimitError(
            f"{path.name} is {duration:.0f}s long, above the "
            f"{config.max_video_duration_seconds:g}s limit "
            f"(raise MCT_MAX_VIDEO_DURATION to allow it)",
            limit_name="MCT_MAX_VIDEO_DURATION",
            limit_value=config.max_video_duration_seconds,
            actual=round(duration, 2),
        )
    width, height = info.get("width") or 0, info.get("height") or 0
    if width > config.max_video_width or height > config.max_video_height:
        raise ResourceLimitError(
            f"{path.name} is {width}x{height}, above the configured "
            f"{config.max_video_width}x{config.max_video_height} limit",
            limit_name="MCT_MAX_VIDEO_WIDTH/HEIGHT",
            limit_value=[config.max_video_width, config.max_video_height],
            actual=[width, height],
        )


def _load_video(path_arg: str, config: Config, field: str = "video_path") -> tuple[Path, dict]:
    source = resolve_input(path_arg, config, field)
    info = describe(source, config)
    if info["kind"] not in ("video", "audio"):
        article = "an" if info["kind"][0] in "aeiou" else "a"
        raise InvalidInputError(
            f"{source.name} is {article} {info['kind']}, not a video or audio file."
        )
    _check_video_limits(info, config, source)
    return source, info


def video_thumbnail(
    video_path: str,
    timestamp: str = "00:00:01",
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    config, manager = _context(config)
    source, info = _load_video(video_path, config)
    if not info.get("has_video"):
        raise InvalidInputError(f"{source.name} has no video stream to take a frame from.")
    stamp = require_timestamp(timestamp, "timestamp")

    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("thumb", "png", destination) as staged:
        ffmpeg.run_ffmpeg(
            ["-ss", stamp, "-i", str(source), "-frames:v", "1", str(staged.tmp)],
            config, what="thumbnail extraction",
        )

    return results.build(
        "video_thumbnail", staged.path, config=config,
        input=str(source), timestamp=stamp,
        width=info.get("width"), height=info.get("height"),
    )


def video_to_gif(
    video_path: str,
    start: str = "00:00:00",
    duration: float = 3.0,
    fps: int = 12,
    width: int = 480,
    loop: int = 0,
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    """Two-pass palette GIF. Bounded so a stray argument cannot make a 2 GB file."""
    config, manager = _context(config)
    source, info = _load_video(video_path, config)
    if not info.get("has_video"):
        raise InvalidInputError(f"{source.name} has no video stream to convert.")

    start_stamp = require_timestamp(start, "start")
    duration = require_positive_number(duration, "duration", maximum=config.max_gif_duration_seconds)
    fps = require_positive_int(fps, "fps", maximum=config.max_gif_fps)
    width = require_positive_int(width, "width", maximum=config.max_gif_width)
    if not isinstance(loop, int) or isinstance(loop, bool) or loop < -1:
        raise InvalidInputError(f"loop must be -1 (no loop), 0 (forever) or a positive count, got {loop!r}")

    # A GIF is uncompressed-ish per frame: fps * duration * width^2 grows fast
    # enough that the individual limits above are not sufficient on their own.
    estimated_frames = int(fps * duration)
    if estimated_frames > 900:
        raise ResourceLimitError(
            f"That would produce about {estimated_frames} frames "
            f"({fps} fps x {duration:g}s). Lower the fps or the duration - GIF is "
            f"a poor format above a few hundred frames.",
            limit_name="fps * duration",
            limit_value=900,
            actual=estimated_frames,
        )

    scale = f"fps={fps},scale={width}:-1:flags=lanczos"
    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None

    with scratch_file(manager, "palette", "png") as palette:
        ffmpeg.run_ffmpeg(
            ["-ss", start_stamp, "-t", f"{duration:g}", "-i", str(source),
             "-vf", f"{scale},palettegen", str(palette)],
            config, what="GIF palette generation",
        )
        with manager.stage("clip", "gif", destination) as staged:
            ffmpeg.run_ffmpeg(
                ["-ss", start_stamp, "-t", f"{duration:g}", "-i", str(source), "-i", str(palette),
                 "-lavfi", f"{scale}[x];[x][1:v]paletteuse", "-loop", str(loop), str(staged.tmp)],
                config, what="GIF encoding",
            )

    return results.build(
        "video_to_gif", staged.path, config=config,
        input=str(source), start=start_stamp, duration=duration,
        fps=fps, width=width, loop=loop, estimated_frames=estimated_frames,
    )


def video_trim(
    video_path: str,
    start: str,
    duration: float,
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    """Cut a clip. Stream-copy first; re-encode only when the copy lands short."""
    config, manager = _context(config)
    source, info = _load_video(video_path, config)
    start_stamp = require_timestamp(start, "start")
    duration = require_positive_number(duration, "duration", maximum=config.max_video_duration_seconds)

    ext = (source.suffix.lstrip(".") or "mp4").lower()
    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None

    method = "stream-copy"
    notes: list[str] = []
    try:
        with manager.stage("trimmed", ext, destination) as staged:
            ffmpeg.run_ffmpeg(
                ["-ss", start_stamp, "-i", str(source), "-t", f"{duration:g}",
                 "-c", "copy", str(staged.tmp)],
                config, what="stream-copy trim",
            )
            # -c copy can exit 0 while landing on the nearest keyframe, giving
            # a clip noticeably shorter than asked for. Measure, do not assume.
            actual = ffmpeg.duration_seconds(staged.tmp, config)
            if actual is None or actual < duration * 0.9:
                raise _ShortCopy(actual)
    except (_ShortCopy, ExternalToolError) as exc:
        method = "re-encode"
        if isinstance(exc, _ShortCopy):
            notes.append(
                f"Stream copy produced {exc.actual if exc.actual is not None else 'an unmeasurable'} "
                f"seconds instead of {duration:g}s because the cut point is not on a "
                f"keyframe, so the clip was re-encoded instead."
            )
        else:
            notes.append("Stream copy failed for this container, so the clip was re-encoded.")
        with manager.stage("trimmed", ext, destination) as staged:
            ffmpeg.run_ffmpeg(
                ["-ss", start_stamp, "-i", str(source), "-t", f"{duration:g}", str(staged.tmp)],
                config, what="re-encoding trim",
            )

    actual = ffmpeg.duration_seconds(staged.path, config)
    return results.build(
        "video_trim", staged.path, config=config,
        input=str(source), start=start_stamp, requested_duration=duration,
        actual_duration=round(actual, 3) if actual is not None else None,
        method=method, notes=notes,
    )


class _ShortCopy(Exception):
    def __init__(self, actual: float | None) -> None:
        super().__init__("stream copy landed short")
        self.actual = round(actual, 3) if actual is not None else None


def video_resize(
    video_path: str,
    width: int,
    height: int | None = None,
    keep_aspect: bool = True,
    crf: int = 23,
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    config, manager = _context(config)
    source, info = _load_video(video_path, config)
    if not info.get("has_video"):
        raise InvalidInputError(f"{source.name} has no video stream to resize.")
    width = require_positive_int(width, "width", maximum=config.max_video_width)
    if height is not None:
        height = require_positive_int(height, "height", maximum=config.max_video_height)
    crf = require_positive_int(crf, "crf", maximum=51)

    # H.264 requires *both* dimensions to be even. ffmpeg's -2 placeholder
    # only evens the dimension it computes, so an odd explicit width still
    # fails with "width not divisible by 2" - snap it here instead, and say so.
    notes: list[str] = []
    even_width = width - (width % 2)
    if even_width != width:
        notes.append(
            f"Width {width} was rounded down to {even_width}: H.264 requires even "
            f"dimensions."
        )
    even_width = max(2, even_width)

    if keep_aspect or height is None:
        scale = f"scale={even_width}:-2:flags=lanczos"
    else:
        even_height = max(2, height - (height % 2))
        if even_height != height:
            notes.append(
                f"Height {height} was rounded down to {even_height}: H.264 requires "
                f"even dimensions."
            )
        scale = f"scale={even_width}:{even_height}:flags=lanczos"

    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("resized", "mp4", destination) as staged:
        ffmpeg.run_ffmpeg(
            ["-i", str(source), "-vf", scale, "-c:v", "libx264", "-crf", str(crf),
             "-preset", "medium", "-pix_fmt", "yuv420p",
             *(["-c:a", "aac", "-b:a", "128k"] if info.get("has_audio") else ["-an"]),
             str(staged.tmp)],
            config, what="video resize",
        )

    out_info = describe(staged.path, config)
    return results.build(
        "video_resize", staged.path, config=config,
        input=str(source),
        input_width=info.get("width"), input_height=info.get("height"),
        actual_width=out_info.get("width"), actual_height=out_info.get("height"),
        crf=crf, notes=notes,
        input_size_bytes=source.stat().st_size,
        size_change_percent=results.percent_change(source.stat().st_size, staged.path.stat().st_size),
    )


def video_compress(
    video_path: str,
    crf: int = 28,
    preset: str = "medium",
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    """Re-encode to H.264/AAC. Lossy, and the result says so."""
    config, manager = _context(config)
    source, info = _load_video(video_path, config)
    if not info.get("has_video"):
        raise InvalidInputError(f"{source.name} has no video stream to compress.")
    crf = require_positive_int(crf, "crf", maximum=51)
    preset = require_choice(
        preset, "preset",
        {"ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"},
    )

    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("compressed", "mp4", destination) as staged:
        ffmpeg.run_ffmpeg(
            ["-i", str(source), "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
             "-pix_fmt", "yuv420p",
             *(["-c:a", "aac", "-b:a", "128k"] if info.get("has_audio") else ["-an"]),
             str(staged.tmp)],
            config, what="video compression",
        )

    input_size = source.stat().st_size
    output_size = staged.path.stat().st_size
    return results.build(
        "video_compress", staged.path, config=config,
        input=str(source), crf=crf, preset=preset,
        input_size_bytes=input_size,
        size_change_percent=results.percent_change(input_size, output_size),
        quality_notes=[
            f"Re-encoded with H.264 at CRF {crf}. This is lossy: quality is reduced "
            f"even where the file grew. Lower CRF means higher quality and a larger file.",
        ]
        + ([
            f"The output is larger than the input, which happens when the source was "
            f"already efficiently encoded. Keep the original."
        ] if output_size > input_size else []),
    )


def extract_audio(
    video_path: str,
    audio_format: str = "mp3",
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    config, manager = _context(config)
    source, info = _load_video(video_path, config)
    fmt = require_choice(audio_format, "audio_format", AUDIO_FORMATS)
    if not info.get("has_audio"):
        raise InvalidInputError(
            f"{source.name} has no audio stream, so there is nothing to extract."
        )

    codec_args = ["-acodec", "libmp3lame", "-q:a", "2"] if fmt == "mp3" else ["-acodec", "pcm_s16le"]
    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("audio", fmt, destination) as staged:
        ffmpeg.run_ffmpeg(
            ["-i", str(source), "-vn", *codec_args, str(staged.tmp)],
            config, what="audio extraction",
        )

    return results.build(
        "extract_audio", staged.path, config=config,
        input=str(source), format=fmt,
        source_codec=info.get("audio_codec"),
        sample_rate=info.get("sample_rate"), channels=info.get("channels"),
    )
