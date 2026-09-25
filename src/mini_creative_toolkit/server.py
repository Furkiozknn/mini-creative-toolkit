"""The MCP server: registration and tool descriptions, no business logic.

Every function here is a thin wrapper over :mod:`mini_creative_toolkit.tools`,
which is also what the CLI calls. The wrappers exist for one reason: an MCP
tool description is what a model reads to decide whether to call the tool, so
each description states what runs where, what it needs, and what it costs.
The capability footer on each one is generated from
:mod:`mini_creative_toolkit.capabilities`, so the description can never drift
away from the declared requirements.
"""

from __future__ import annotations

import functools
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__
from .capabilities import CAPABILITIES, NetworkNeed
from .config import get_config
from .errors import ToolkitError
from .log import configure, get_logger
from .paths import OutputManager
from .tools import background as background_tools
from .tools import batch as batch_tools
from .tools import generate as generate_tools
from .tools import image as image_tools
from .tools import inspect as inspect_tools
from .tools import optimize as optimize_tools
from .tools import presets as preset_tools
from .tools import upscale as upscale_tools
from .tools import video as video_tools

logger = get_logger(__name__)

mcp = MCPServer(
    "mini-creative-toolkit",
    title="Mini Creative Toolkit",
    version=__version__,
    instructions=(
        "Local media operations for images, video and audio. Everything runs on this "
        "machine except generate_image_free, which calls a third-party service and "
        "says so; remove_background downloads a model's weights the first time that "
        "model is used. Call list_capabilities first if you need to know what this "
        "installation can actually do - it reports which tools are ready and which "
        "are missing ffmpeg, a GPU or an Upscayl install."
    ),
)


# --- shared parameter descriptions -------------------------------------------
# These land in each tool's JSON schema, which is what a model reads when it
# fills in arguments. Written once so twenty tools cannot drift apart.

_FILE = (
    "Path to an existing local file. Absolute paths are safest; a relative path "
    "resolves against the server's working directory. Symlinks are followed, and "
    "the real target must lie inside MCT_ALLOWED_ROOTS when that is set."
)
ImagePath = Annotated[str, Field(description=f"The image to read. {_FILE}")]
VideoPath = Annotated[str, Field(description=f"The video (or audio) file to read. {_FILE}")]
MediaPath = Annotated[str, Field(description=f"The image, video or audio file to read. {_FILE}")]
OutputPath = Annotated[
    str | None,
    Field(
        description=(
            "Where to write the result. Omit it to get a fresh, never-colliding name "
            "in MCT_OUTPUT_DIR (the result reports it). Its directory must already "
            "exist; an existing file is refused unless overwrite is true."
        )
    ),
]
Overwrite = Annotated[
    bool,
    Field(description="Allow output_path to replace an existing file. Default false."),
]
Timestamp = Annotated[
    str,
    Field(description="Position in the video: HH:MM:SS, MM:SS, or a number of seconds."),
]


def _annotations(name: str) -> ToolAnnotations:
    """MCP tool hints, derived from the capability table like the footer."""
    cap = CAPABILITIES[name]
    return ToolAnnotations(
        read_only_hint=not cap.writes_files,
        open_world_hint=cap.network is not NetworkNeed.NONE,
    )


def describe(name: str, body: str) -> str:
    """Tool description = human explanation + generated capability footer."""
    cap = CAPABILITIES.get(name)
    if cap is None:  # pragma: no cover - every registered tool is in the table
        return body
    footer = cap.description_footer()
    notes = "".join(f"\n{note}" for note in cap.notes)
    return f"{body.strip()}\n\n[{footer}]{notes}"


def _tool(name: str, body: str):
    """Register a tool, translating this project's errors into MCP's.

    The SDK treats any exception that is not a ``ToolError`` as a crash and
    replaces its text with "Error executing tool <name>" - correct for an
    unexpected exception, but wrong for every error this project raises
    deliberately. "No such file: /x.png" and "UPSCAYL_BIN_PATH is not set,
    use upscale_image_fast instead" are written for a model to read and act
    on; losing them would waste the whole error-message design.

    A genuinely unexpected exception is deliberately *not* translated - it
    keeps the SDK's default masking and full server-side traceback.
    """
    register = mcp.tool(name=name, description=describe(name, body), annotations=_annotations(name))

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ToolkitError as exc:
                raise ToolError(exc.describe(get_config().verbose)) from exc

        return register(wrapper)

    return decorator


# --- discovery ---------------------------------------------------------------

@_tool(
    "list_capabilities",
    "Report every tool in this server, what it requires (local or hosted, network, "
    "GPU, external binary, model), and whether this machine can currently run it. "
    "Also reports the configured resource limits. Call this when a tool fails with a "
    "missing-dependency error, or before planning a multi-step job.",
)
def list_capabilities() -> dict:
    return inspect_tools.list_capabilities()


@_tool(
    "list_background_models",
    "List the background-removal models available to this rembg installation, with "
    "size, rough speed, and licence status. Models whose licence has not been "
    "verified against a primary source say 'not verified' rather than guessing - "
    "check before commercial use.",
)
def list_background_models() -> dict:
    return background_tools.list_background_models()


@_tool(
    "list_presets",
    "List the built-in image and video dimension presets (square, portrait, story, "
    "vertical, and so on). These are a convenience, not a platform certification.",
)
def list_presets() -> dict:
    return preset_tools.list_presets()


@_tool(
    "inspect_media",
    "Describe a media file without changing it. For images: format, dimensions, "
    "aspect ratio, colour mode, alpha, EXIF/ICC presence, frame count. For video: "
    "container, duration, dimensions, fps, video and audio codecs, bitrate, frame "
    "count. For audio: codec, duration, sample rate, channels. Use this before "
    "deciding how to process something rather than guessing from the file extension.",
)
def inspect_media(path: MediaPath) -> dict:
    return inspect_tools.inspect_media(path)


# --- images ------------------------------------------------------------------

@_tool(
    "resize_image",
    "Resize an image with Lanczos resampling. By default it fits the image inside "
    "the given width and height without distorting it, so the result may be smaller "
    "than requested in one dimension; pass keep_aspect=false to stretch to exactly "
    "width x height. Returns the output path and the dimensions actually produced.",
)
def resize_image(
    image_path: ImagePath,
    width: Annotated[int, Field(description="Target width in pixels, 1 to 100000.")],
    height: Annotated[int, Field(description="Target height in pixels, 1 to 100000.")],
    keep_aspect: Annotated[
        bool,
        Field(
            description=(
                "Fit inside width x height keeping the aspect ratio. Default true; false "
                "stretches to exactly width x height."
            )
        ),
    ] = True,
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return image_tools.resize_image(image_path, width, height, keep_aspect, output_path, overwrite)


@_tool(
    "convert_format",
    "Re-encode an image to png, jpeg, webp, or avif (avif only if this Pillow build "
    "supports it - list_capabilities reports which formats are writable). quality "
    "applies to lossy formats; lossless=true applies to webp and avif. Converting an "
    "image with transparency to jpeg flattens it onto the background colour and says "
    "so in the result rather than dropping alpha silently.",
)
def convert_format(
    image_path: ImagePath,
    target_format: Annotated[
        str,
        Field(description="Format to write: png, jpeg (or jpg), webp, or avif. Case does not matter."),
    ],
    quality: Annotated[
        int | None,
        Field(
            description=(
                "Encoder quality for jpeg, webp and avif, 1 to 100. Ignored for png. "
                "Omit it for the encoder default (90 for jpeg)."
            )
        ),
    ] = None,
    lossless: Annotated[
        bool,
        Field(
            description=(
                "Encode webp or avif losslessly; quality is then ignored. Has no effect "
                "on other formats. Default false."
            )
        ),
    ] = False,
    background: Annotated[
        str,
        Field(
            description=(
                "Colour that transparency is flattened onto when converting to jpeg: "
                "white, black, grey (or gray), or #rrggbb. Default white."
            )
        ),
    ] = "white",
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return image_tools.convert_format(
        image_path, target_format, quality, lossless, background, output_path, overwrite
    )


@_tool(
    "strip_metadata",
    "Remove all metadata from an image - EXIF (including GPS coordinates, camera "
    "model and timestamps), ICC profiles, XMP and PNG text chunks - by rebuilding the "
    "file from raw pixel data. A privacy tool, not a creative one. The result lists "
    "what was actually removed.",
)
def strip_metadata(
    image_path: ImagePath, output_path: OutputPath = None, overwrite: Overwrite = False
) -> dict | str:
    return image_tools.strip_metadata(image_path, output_path, overwrite)


@_tool(
    "add_watermark",
    "Draw semi-transparent text onto an image at a chosen corner or the centre. "
    "position is top-left, top-right, bottom-left, bottom-right or center; opacity "
    "runs 0 (invisible) to 1 (solid). This overlays text - it is not a filter and "
    "does not modify the underlying pixels' content.",
)
def add_watermark(
    image_path: ImagePath,
    text: Annotated[
        str,
        Field(description="Watermark text, drawn in white. 1 to 200 characters, no control characters."),
    ],
    position: Annotated[
        str,
        Field(
            description=(
                "Where to place the text: top-left, top-right, bottom-left, bottom-right "
                "or center. Default bottom-right."
            )
        ),
    ] = "bottom-right",
    opacity: Annotated[
        float,
        Field(description="Text opacity from 0 (invisible) to 1 (solid). Default 0.5."),
    ] = 0.5,
    font_size: Annotated[
        int,
        Field(description="Font size in pixels, 1 to 2000. Default 24."),
    ] = 24,
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return image_tools.add_watermark(
        image_path, text, position, opacity, font_size, output_path, overwrite
    )


@_tool(
    "remove_background",
    "Cut the subject out of an image and save it as a transparent PNG. The default "
    "model is u2net (Apache-2.0, fast). Pass birefnet-general for noticeably better "
    "hair and fine-edge quality at the cost of a large one-time weights download and "
    "much slower CPU inference. The model name is always explicit; this tool never "
    "falls back to rembg's own internal default.",
)
def remove_background(
    image_path: ImagePath,
    model: Annotated[
        str,
        Field(
            description=(
                "rembg model name, for example u2net (default) or birefnet-general. "
                "list_background_models shows the choices; an unknown name is refused."
            )
        ),
    ] = "u2net",
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return background_tools.remove_background(image_path, model, output_path, overwrite)


@_tool(
    "create_contact_sheet",
    "Tile several images into one sheet for review, with optional filename labels. "
    "Useful for comparing a batch of generated images at a glance. Images that cannot "
    "be read are skipped and listed rather than aborting the sheet.",
)
def create_contact_sheet(
    image_paths: Annotated[
        list[str],
        Field(
            description=(
                "Local image files to tile, in order. At least one, at most "
                "MCT_MAX_BATCH_ITEMS (default 200). Same path rules as image_path."
            )
        ),
    ],
    thumbnail_size: Annotated[
        int,
        Field(description="Longest side of each thumbnail in pixels, 1 to 2000. Default 240."),
    ] = 240,
    columns: Annotated[
        int,
        Field(description="Number of thumbnails per row, 1 to 20. Default 4."),
    ] = 4,
    padding: Annotated[
        int,
        Field(description="Space between and around thumbnails in pixels, 0 to 200. Default 12."),
    ] = 12,
    labels: Annotated[
        bool,
        Field(description="Print each file name under its thumbnail. Default true."),
    ] = True,
    background: Annotated[
        str,
        Field(
            description=(
                "Sheet background colour: white, black, grey (or gray), or #rrggbb. "
                "Default white."
            )
        ),
    ] = "white",
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return image_tools.create_contact_sheet(
        image_paths, thumbnail_size, columns, padding, labels, background, output_path, overwrite
    )


@_tool(
    "compare_images",
    "Compare two images: dimensions, format, file size, SHA-256, and a coarse mean "
    "pixel difference computed on 64x64 thumbnails. Byte equality is exact; the "
    "similarity score is a rough guide only and is explicitly not forensic evidence "
    "of identity or provenance. Writes nothing.",
)
def compare_images(
    image_a: Annotated[str, Field(description=f"First image. {_FILE}")],
    image_b: Annotated[str, Field(description=f"Second image. {_FILE}")],
) -> dict:
    return image_tools.compare_images(image_a, image_b)


# --- upscaling ---------------------------------------------------------------

@_tool(
    "upscale_image_fast",
    "Upscale an image 2x, 3x or 4x with FSRCNN, a small pretrained super-resolution "
    "network that runs on CPU in well under a second. Meaningfully sharper edges than "
    "a plain resize. It does NOT hallucinate texture the way Real-ESRGAN does - for "
    "that quality you need upscale_image and a discrete GPU. This is the practical "
    "default on machines without one.",
)
def upscale_image_fast(
    image_path: ImagePath,
    scale: Annotated[
        int,
        Field(description="Enlargement factor: 2, 3 or 4 (one FSRCNN model per factor). Default 4."),
    ] = 4,
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return upscale_tools.upscale_image_fast(image_path, scale, output_path, overwrite)


@_tool(
    "upscale_image",
    "Upscale an image with Real-ESRGAN through a local Upscayl install. This is the "
    "highest-quality option and the only one that invents plausible new detail, but "
    "it needs a discrete GPU: on integrated graphics a single small icon was measured "
    "at over seven minutes without finishing. Requires UPSCAYL_BIN_PATH and "
    "UPSCAYL_MODELS_PATH; nothing is downloaded automatically. Prefer "
    "upscale_image_auto unless you specifically want this method.",
)
def upscale_image(
    image_path: ImagePath,
    scale: Annotated[
        int,
        Field(description="Enlargement factor: 2, 3 or 4. Default 4."),
    ] = 4,
    model: Annotated[
        str,
        Field(
            description=(
                "Upscayl model name, as found in UPSCAYL_MODELS_PATH. Letters, digits, "
                "'-' and '_' only. Default upscayl-standard-4x."
            )
        ),
    ] = "upscayl-standard-4x",
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return upscale_tools.upscale_image(image_path, scale, model, output_path, overwrite)


@_tool(
    "upscale_image_auto",
    "Upscale an image with the best method this machine can actually run, and report "
    "which one was chosen and why. Picks Real-ESRGAN when Upscayl is configured and a "
    "discrete GPU is present, FSRCNN otherwise, and plain Lanczos for enlargements "
    "too small to benefit from a model. The methods are not equivalent in quality and "
    "the result says so.",
)
def upscale_image_auto(
    image_path: ImagePath,
    scale: Annotated[
        int,
        Field(
            description=(
                "Whole-number enlargement factor, 1 to 8. Default 4. The models only "
                "cover 2x, 3x and 4x; other factors use Lanczos."
            )
        ),
    ] = 4,
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return upscale_tools.upscale_image_auto(image_path, scale, output_path, overwrite)


# --- video and audio ---------------------------------------------------------

@_tool(
    "video_thumbnail",
    "Extract a single frame from a video as a PNG. timestamp is HH:MM:SS, MM:SS or a "
    "number of seconds. Requires ffmpeg on PATH.",
)
def video_thumbnail(
    video_path: VideoPath,
    timestamp: Timestamp = "00:00:01",
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return video_tools.video_thumbnail(video_path, timestamp, output_path, overwrite)


@_tool(
    "video_to_gif",
    "Convert part of a video to an optimised GIF using a two-pass palette, which "
    "gives far better colour than a naive conversion. Duration, fps and width are "
    "capped, and a request whose fps x duration would produce an unreasonable number "
    "of frames is refused rather than silently producing a huge file. Requires ffmpeg.",
)
def video_to_gif(
    video_path: VideoPath,
    start: Timestamp = "00:00:00",
    duration: Annotated[
        float,
        Field(
            description=(
                "Length of the clip in seconds, above 0 and at most 30. "
                "fps x duration must not exceed 900 frames. Default 3."
            )
        ),
    ] = 3.0,
    fps: Annotated[
        int,
        Field(description="Frames per second in the GIF, 1 to 50. Default 12."),
    ] = 12,
    width: Annotated[
        int,
        Field(
            description=(
                "GIF width in pixels, 1 to 1920; height follows the aspect "
                "ratio. Default 480."
            )
        ),
    ] = 480,
    loop: Annotated[
        int,
        Field(description="0 loops forever (default), -1 plays once, a positive number repeats that many times."),
    ] = 0,
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return video_tools.video_to_gif(
        video_path, start, duration, fps, width, loop, output_path, overwrite
    )


@_tool(
    "video_trim",
    "Cut a clip out of a video. Tries a lossless stream copy first, which is fast but "
    "can only cut on keyframes; if the copy lands short of the requested duration the "
    "clip is re-encoded instead. The result reports which method was used. Requires "
    "ffmpeg and ffprobe.",
)
def video_trim(
    video_path: VideoPath,
    start: Timestamp,
    duration: Annotated[
        float,
        Field(
            description=(
                "Length of the clip in seconds, above 0 and at most MCT_MAX_VIDEO_DURATION "
                "(default 3600)."
            )
        ),
    ],
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return video_tools.video_trim(video_path, start, duration, output_path, overwrite)


@_tool(
    "video_resize",
    "Scale a video to a target width, preserving aspect ratio by default and always "
    "producing even dimensions (H.264 requires them). This re-encodes, so it is lossy "
    "and slower than a trim. Requires ffmpeg and ffprobe.",
)
def video_resize(
    video_path: VideoPath,
    width: Annotated[
        int,
        Field(
            description=(
                "Target width in pixels, up to MCT_MAX_VIDEO_WIDTH (default 7680). An odd "
                "value is rounded down to even."
            )
        ),
    ],
    height: Annotated[
        int | None,
        Field(
            description=(
                "Target height in pixels, used only when keep_aspect is false. Omit it to "
                "derive the height from the aspect ratio."
            )
        ),
    ] = None,
    keep_aspect: Annotated[
        bool,
        Field(
            description=(
                "Derive the height from width and the source aspect ratio. Default true; "
                "false with a height stretches to exactly width x height."
            )
        ),
    ] = True,
    crf: Annotated[
        int,
        Field(
            description=(
                "H.264 constant rate factor, 1 to 51. Lower means better quality and a "
                "larger file. Default 23."
            )
        ),
    ] = 23,
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return video_tools.video_resize(
        video_path, width, height, keep_aspect, crf, output_path, overwrite
    )


@_tool(
    "video_compress",
    "Re-encode a video to H.264/AAC at a chosen CRF (lower means better quality and a "
    "larger file; 23 is a reasonable default, 28 is noticeably smaller). This is "
    "lossy. If the output ends up larger than the input - which happens when the "
    "source was already well encoded - the result says so instead of reporting a "
    "'saving'. Requires ffmpeg and ffprobe.",
)
def video_compress(
    video_path: VideoPath,
    crf: Annotated[
        int,
        Field(
            description=(
                "H.264 constant rate factor, 1 to 51. Lower means better quality and a "
                "larger file. Default 28."
            )
        ),
    ] = 28,
    preset: Annotated[
        str,
        Field(
            description=(
                "x264 speed preset: ultrafast, superfast, veryfast, faster, fast, medium, "
                "slow, slower or veryslow. Slower gives a smaller file. Default medium."
            )
        ),
    ] = "medium",
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return video_tools.video_compress(video_path, crf, preset, output_path, overwrite)


@_tool(
    "extract_audio",
    "Pull the audio track out of a video as mp3 or wav. Fails with a clear message if "
    "the file has no audio stream rather than producing an empty file. Requires ffmpeg.",
)
def extract_audio(
    video_path: VideoPath,
    audio_format: Annotated[
        str,
        Field(description="mp3 (variable bitrate) or wav (16-bit PCM). Default mp3."),
    ] = "mp3",
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return video_tools.extract_audio(video_path, audio_format, output_path, overwrite)


# --- higher-level ------------------------------------------------------------

@_tool(
    "optimize_media",
    "Inspect a file, then choose and apply a deterministic optimisation for a stated "
    "goal: web, social, smallest, quality, or archive. For images this picks a format "
    "and quality and can fit the result to a preset or explicit maximum dimensions; "
    "for video it re-encodes at a goal-appropriate CRF. The result lists every "
    "operation applied and every quality trade-off made - nothing is degraded "
    "silently, and a result that came out larger than the input says so.",
)
def optimize_media(
    path: MediaPath,
    goal: Annotated[
        str,
        Field(description="What to optimise for: web, social, smallest, quality or archive. Default web."),
    ] = "web",
    max_width: Annotated[
        int | None,
        Field(
            description=(
                "Images only: fit the result within this width in pixels, keeping the "
                "aspect ratio. 1 to 100000."
            )
        ),
    ] = None,
    max_height: Annotated[
        int | None,
        Field(
            description=(
                "Images only: fit the result within this height in pixels, keeping the "
                "aspect ratio. 1 to 100000."
            )
        ),
    ] = None,
    preset: Annotated[
        str | None,
        Field(
            description=(
                "Images only: an image preset name from list_presets (square, portrait, "
                "landscape, story, wide, thumbnail). Replaces max_width and max_height."
            )
        ),
    ] = None,
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return optimize_tools.optimize_media(
        path, goal, max_width, max_height, preset, output_path, overwrite
    )


@_tool(
    "batch_process",
    "Apply one operation to many files with bounded concurrency. operation is one of "
    "resize, convert_format, strip_metadata, watermark, remove_background, optimize, "
    "upscale_fast; options carries that operation's arguments (for example "
    "{\"width\": 1080, \"height\": 1080} for resize). A file that fails does not abort "
    "the batch - it is reported in 'errors' while the rest continue. Each file gets "
    "its own generated output path, so nothing is overwritten.",
)
def batch_process(
    paths: Annotated[
        list[str],
        Field(
            description=(
                "Local files to process. At least one, at most MCT_MAX_BATCH_ITEMS "
                "(default 200). Same path rules as image_path."
            )
        ),
    ],
    operation: Annotated[
        str,
        Field(
            description=(
                "One of resize, convert_format, strip_metadata, watermark, "
                "remove_background, optimize, upscale_fast."
            )
        ),
    ],
    options: Annotated[
        dict | None,
        Field(
            description=(
                "Keyword arguments for the operation, named as in the single-file tool. "
                "resize needs width and height, convert_format needs target_format, "
                "watermark needs text. output_path is not allowed."
            )
        ),
    ] = None,
    concurrency: Annotated[
        int | None,
        Field(
            description=(
                "Files processed at once. Omit for the cap: 4 (MCT_BATCH_CONCURRENCY), "
                "or 2 for remove_background and upscale_fast (MCT_HEAVY_BATCH_CONCURRENCY). "
                "A higher value is refused."
            )
        ),
    ] = None,
) -> dict:
    return batch_tools.batch_process(paths, operation, options, concurrency)


# --- hosted ------------------------------------------------------------------

@_tool(
    "generate_image_free",
    "Generate an image from a text prompt. THIS IS THE ONLY TOOL THAT LEAVES THIS "
    "MACHINE: the prompt text is sent to Pollinations.ai, a third-party service, over "
    "the network. No API key or account is needed today, but that is the service's "
    "current policy and not a guarantee. Do not use it for prompts containing "
    "confidential information. Every other tool runs on this machine and sends "
    "none of your data anywhere; remove_background only downloads model weights "
    "the first time a model is used.",
)
def generate_image_free(
    prompt: Annotated[
        str,
        Field(
            description=(
                "Text description of the image, 1 to 1000 characters, no control "
                "characters. It is sent to Pollinations.ai."
            )
        ),
    ],
    width: Annotated[
        int,
        Field(description="Requested width in pixels, 1 to 4096. Default 1024."),
    ] = 1024,
    height: Annotated[
        int,
        Field(description="Requested height in pixels, 1 to 4096. Default 1024."),
    ] = 1024,
    seed: Annotated[
        int | None,
        Field(
            description=(
                "Seed for repeatable output, 1 to 2147483647. Omit it to let the service "
                "choose."
            )
        ),
    ] = None,
    output_path: OutputPath = None,
    overwrite: Overwrite = False,
) -> dict | str:
    return generate_tools.generate_image_free(prompt, width, height, seed, output_path, overwrite)


def main() -> None:
    """Start the stdio MCP server."""
    config = get_config()
    configure(config.log_level)
    removed = 0
    try:
        removed = OutputManager(config).cleanup_partials()
    except Exception:  # pragma: no cover - never block startup on housekeeping
        logger.debug("partial-file cleanup failed", exc_info=True)
    if removed:
        logger.info("Removed %d leftover partial file(s) from a previous run", removed)
    logger.info("mini-creative-toolkit MCP server starting (output dir: %s)", config.output_dir)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
