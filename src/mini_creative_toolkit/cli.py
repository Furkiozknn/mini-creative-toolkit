"""``mct`` - the same operations from a shell.

The CLI is deliberately a thin adapter: it parses flags, calls exactly the
same functions in :mod:`mini_creative_toolkit.tools` that the MCP server
calls, and prints their structured result. There is no second implementation
of any rule here, which is why the two surfaces cannot disagree.

``allow_abbrev=False`` everywhere: argparse's default prefix matching means
``--width`` would silently resolve to ``--width-limit`` if such a flag were
ever added, and a resize that quietly used the wrong argument is worse than
one that errors.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .config import Config, get_config, set_config
from .errors import InvalidInputError, ToolkitError
from .log import configure, get_logger
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

EXIT_OK = 0
EXIT_TOOL_ERROR = 1
EXIT_USAGE = 2

EPILOG = """\
first steps:
  mct inspect photo.jpg                 what the file really is (never modifies it)
  mct strip-metadata photo.jpg          drop EXIF/GPS; writes a new file, lists what went
  mct optimize photo.jpg --goal web     smaller file, every trade-off reported
  mct capabilities                      what this machine can and cannot run
  mct serve                             start the MCP server on stdio

Results are written to MCT_OUTPUT_DIR (default ./output) or to -o PATH; an
input is never changed. Add --json for the structured result.
Every command prints "execution" and "network". Only 'generate' sends your data
out; 'remove-bg' downloads a model's weights the first time that model is used.
Exit codes: 0 done, 1 the operation failed (reason on stderr), 2 usage error.
"""

#: Help for arguments that would otherwise show a bare name in `mct <cmd> --help`.
#: Applied only where a command did not write its own help text.
_ARG_HELP = {
    "path": "file to read (never modified)",
    "paths": "files to read; wildcards such as *.jpg work on every shell",
    "image_a": "first image",
    "image_b": "second image",
    "width": "width in pixels",
    "height": "height in pixels",
    "start": "start time: HH:MM:SS, MM:SS or seconds",
    "duration": "length in seconds",
    "timestamp": "moment to grab: HH:MM:SS, MM:SS or seconds",
    "crf": "H.264 quality: lower means better quality and a larger file",
    "fps": "frames per second",
    "quality": "1-100, for lossy formats",
    "text": "the text to draw",
    "opacity": "0 (invisible) to 1 (solid)",
    "font_size": "size in points",
    "scale": "enlargement factor: 2, 3 or 4 use the FSRCNN model",
    "model": "model name (see 'mct models')",
    "prompt": "text prompt; it is sent to a third party",
    "seed": "fixed seed for a repeatable result",
    "loop": "GIF loops (0 = forever)",
    "columns": "tiles per row",
    "padding": "pixels between tiles",
    "thumbnail_size": "tile size in pixels",
    "concurrency": "workers (bounded by MCT_BATCH_CONCURRENCY)",
    "preset": "encoder speed preset (ultrafast ... veryslow)",
    "lossless": "lossless encoding (webp and avif only)",
    "goal": "what to optimise for: web, social, smallest, quality or archive",
    "max_width": "fit within this width",
    "max_height": "fit within this height",
    "position": "where to draw the text",
    "audio_format": "mp3 or wav",
    "no_labels": "leave file names off the tiles",
    "operation": "what to do to every file: " + ", ".join(sorted(batch_tools.OPERATIONS)),
}


class _Parser(argparse.ArgumentParser):
    """Exit code 2 for usage errors, matching the documented contract."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _global_flags(suppress: bool) -> argparse.ArgumentParser:
    """The flags that work either side of the subcommand.

    `mct --json capabilities` and `mct capabilities --json` should both work -
    the second is the form people actually type, and requiring the first is a
    papercut with no upside.

    The subparser copies use `default=SUPPRESS` so that omitting a flag after
    the subcommand leaves the value parsed before it alone. Without that,
    argparse's normal defaults would overwrite `--json` back to False and the
    pre-subcommand form would silently stop working.
    """
    parser = argparse.ArgumentParser(add_help=False)
    unset = argparse.SUPPRESS if suppress else None
    parser.add_argument(
        "--log-level", choices=("quiet", "normal", "verbose"),
        default=unset, help="override MCT_LOG_LEVEL",
    )
    parser.add_argument(
        "--output-dir", default=unset, help="override MCT_OUTPUT_DIR for this invocation",
    )
    parser.add_argument(
        "--json", action="store_true",
        default=argparse.SUPPRESS if suppress else False,
        help="print the raw structured result as JSON",
    )
    return parser


#: Added to every subcommand, so the global flags also work after it.
SUBCOMMAND_GLOBALS = _global_flags(suppress=True)


def _sub(subparsers, name: str, help_text: str) -> argparse.ArgumentParser:
    return subparsers.add_parser(
        name, help=help_text, description=help_text, allow_abbrev=False,
        parents=[SUBCOMMAND_GLOBALS],
    )


def _add(subparsers, name: str, help_text: str) -> argparse.ArgumentParser:
    """A subcommand that writes a file, so it also takes -o/--overwrite."""
    parser = _sub(subparsers, name, help_text)
    parser.add_argument("-o", "--output", dest="output_path", help="explicit destination path")
    parser.add_argument(
        "--overwrite", action="store_true", help="allow --output to replace an existing file"
    )
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="mct",
        description=(
            "Local media operations. Everything runs on this machine except "
            "'generate', which calls a third-party service and says so."
        ),
        allow_abbrev=False,
        parents=[_global_flags(suppress=False)],
    )
    parser.epilog = EPILOG
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.add_argument("--version", action="version", version=f"mct {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")

    p = _add(sub, "inspect", "Describe a media file without changing it.")
    p.add_argument("path")

    p = _add(sub, "resize", "Resize an image with Lanczos resampling.")
    p.add_argument("path")
    p.add_argument("--width", type=int, required=True)
    p.add_argument("--height", type=int, required=True)
    p.add_argument("--stretch", action="store_true", help="ignore aspect ratio")

    p = _add(sub, "convert", "Re-encode an image to another format.")
    p.add_argument("path")
    p.add_argument("--format", required=True, help="png, jpeg, webp or avif")
    p.add_argument("--quality", type=int)
    p.add_argument("--lossless", action="store_true")
    p.add_argument("--background", default="white", help="fill colour when flattening alpha")

    p = _add(sub, "optimize", "Inspect, then apply a deterministic optimisation.")
    p.add_argument("path")
    p.add_argument("--goal", default="web", choices=sorted(optimize_tools.GOALS))
    p.add_argument("--max-width", type=int)
    p.add_argument("--max-height", type=int)
    p.add_argument("--preset", help="fit to a named image preset (see 'mct presets')")

    p = _add(sub, "strip-metadata", "Remove EXIF/ICC/XMP and other metadata from an image.")
    p.add_argument("path")

    p = _add(sub, "watermark", "Draw semi-transparent text onto an image.")
    p.add_argument("path")
    p.add_argument("--text", required=True)
    p.add_argument("--position", default="bottom-right", choices=sorted(image_tools.WATERMARK_POSITIONS))
    p.add_argument("--opacity", type=float, default=0.5)
    p.add_argument("--font-size", type=int, default=24)

    p = _add(sub, "remove-bg", "Cut the subject out into a transparent PNG.")
    p.add_argument("path")
    p.add_argument("--model", default="u2net")

    p = _add(sub, "upscale", "Upscale an image with the best available local method.")
    p.add_argument("path")
    p.add_argument("--scale", type=int, default=4)
    p.add_argument(
        "--method", default="auto", choices=("auto", "fsrcnn", "real-esrgan"),
        help="'auto' picks and explains; 'real-esrgan' requires Upscayl and a discrete GPU",
    )
    p.add_argument("--model", default="upscayl-standard-4x", help="Upscayl model name")

    p = _add(sub, "thumbnail", "Grab a single frame from a video.")
    p.add_argument("path")
    p.add_argument("--at", dest="timestamp", default="00:00:01")

    p = _add(sub, "gif", "Convert part of a video to an optimised GIF.")
    p.add_argument("path")
    p.add_argument("--start", default="00:00:00")
    p.add_argument("--duration", type=float, default=3.0)
    p.add_argument("--fps", type=int, default=12)
    p.add_argument("--width", type=int, default=480)
    p.add_argument("--loop", type=int, default=0)

    p = _add(sub, "trim", "Cut a clip out of a video.")
    p.add_argument("path")
    p.add_argument("--start", required=True)
    p.add_argument("--duration", type=float, required=True)

    p = _add(sub, "video-resize", "Scale a video (re-encodes).")
    p.add_argument("path")
    p.add_argument("--width", type=int, required=True)
    p.add_argument("--height", type=int)
    p.add_argument("--crf", type=int, default=23)

    p = _add(sub, "compress", "Re-encode a video to H.264/AAC at a chosen CRF.")
    p.add_argument("path")
    p.add_argument("--crf", type=int, default=28)
    p.add_argument("--preset", default="medium")

    p = _add(sub, "audio", "Extract the audio track from a video.")
    p.add_argument("path")
    p.add_argument("--format", dest="audio_format", default="mp3", choices=sorted(video_tools.AUDIO_FORMATS))

    p = _add(sub, "contact-sheet", "Tile several images into one review sheet.")
    p.add_argument("paths", nargs="+")
    p.add_argument("--thumbnail-size", type=int, default=240)
    p.add_argument("--columns", type=int, default=4)
    p.add_argument("--padding", type=int, default=12)
    p.add_argument("--no-labels", action="store_true")

    p = _sub(sub, "compare", "Compare two images.")
    p.add_argument("image_a")
    p.add_argument("image_b")

    # No -o here: one destination cannot hold many results (use --output-dir).
    p = _sub(sub, "batch", "Apply one operation to many files (results go to --output-dir).")
    p.add_argument("paths", nargs="+")
    p.add_argument("--operation", required=True, choices=sorted(batch_tools.OPERATIONS))
    p.add_argument("--options", default="{}", help="JSON object of operation arguments")
    p.add_argument("--concurrency", type=int)

    p = _add(sub, "generate", "Generate an image from a prompt (HOSTED - leaves this machine).")
    p.add_argument("prompt")
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--height", type=int, default=1024)
    p.add_argument("--seed", type=int)

    _sub(sub, "capabilities", "What every tool needs and what this machine can run.")
    _sub(sub, "presets", "List the built-in dimension presets.")
    _sub(sub, "models", "List background-removal models and their licences.")
    _sub(sub, "serve", "Start the MCP server on stdio.")

    for choice in sub.choices.values():
        for action in choice._actions:
            if action.help is None and action.dest in _ARG_HELP:
                action.help = _ARG_HELP[action.dest]
    return parser


def _expand(patterns: Sequence[str]) -> list[str]:
    """Expand wildcards the shell did not.

    POSIX shells expand ``*.jpg`` before mct starts; cmd.exe and PowerShell
    hand it over literally, and the operation then failed with a localised
    Windows error about a bad file name. A pattern is only expanded when no
    file of that literal name exists, so a file really called ``a[1].png`` is
    still found.
    """
    expanded: list[str] = []
    for raw in patterns:
        if any(ch in raw for ch in "*?[") and not Path(raw).exists():
            hits = sorted(h for h in glob.glob(raw) if Path(h).is_file())
            if not hits:
                raise InvalidInputError(f"no file matches {raw!r}")
            expanded.extend(hits)
        else:
            expanded.append(raw)
    return expanded


def _dispatch(args: argparse.Namespace) -> object:
    out = getattr(args, "output_path", None)
    ow = getattr(args, "overwrite", False)
    command = args.command

    if command == "inspect":
        return inspect_tools.inspect_media(args.path)
    if command == "capabilities":
        return inspect_tools.list_capabilities()
    if command == "presets":
        return preset_tools.list_presets()
    if command == "models":
        return background_tools.list_background_models()
    if command == "resize":
        return image_tools.resize_image(args.path, args.width, args.height, not args.stretch, out, ow)
    if command == "convert":
        return image_tools.convert_format(
            args.path, args.format, args.quality, args.lossless, args.background, out, ow
        )
    if command == "optimize":
        return optimize_tools.optimize_media(
            args.path, args.goal, args.max_width, args.max_height, args.preset, out, ow
        )
    if command == "strip-metadata":
        return image_tools.strip_metadata(args.path, out, ow)
    if command == "watermark":
        return image_tools.add_watermark(
            args.path, args.text, args.position, args.opacity, args.font_size, out, ow
        )
    if command == "remove-bg":
        return background_tools.remove_background(args.path, args.model, out, ow)
    if command == "upscale":
        if args.method == "fsrcnn":
            return upscale_tools.upscale_image_fast(args.path, args.scale, out, ow)
        if args.method == "real-esrgan":
            return upscale_tools.upscale_image(args.path, args.scale, args.model, out, ow)
        return upscale_tools.upscale_image_auto(args.path, args.scale, out, ow)
    if command == "thumbnail":
        return video_tools.video_thumbnail(args.path, args.timestamp, out, ow)
    if command == "gif":
        return video_tools.video_to_gif(
            args.path, args.start, args.duration, args.fps, args.width, args.loop, out, ow
        )
    if command == "trim":
        return video_tools.video_trim(args.path, args.start, args.duration, out, ow)
    if command == "video-resize":
        return video_tools.video_resize(
            args.path, args.width, args.height, args.height is None, args.crf, out, ow
        )
    if command == "compress":
        return video_tools.video_compress(args.path, args.crf, args.preset, out, ow)
    if command == "audio":
        return video_tools.extract_audio(args.path, args.audio_format, out, ow)
    if command == "contact-sheet":
        return image_tools.create_contact_sheet(
            _expand(args.paths), args.thumbnail_size, args.columns, args.padding,
            not args.no_labels, "white", out, ow,
        )
    if command == "compare":
        return image_tools.compare_images(args.image_a, args.image_b)
    if command == "batch":
        try:
            options = json.loads(args.options)
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"mct: --options must be a JSON object: {exc}\n"
                f"     example: --options '{{\"goal\": \"web\"}}'  "
                f"(on Windows cmd/PowerShell wrap it in double quotes and escape the inner ones)"
            )
        return batch_tools.batch_process(_expand(args.paths), args.operation, options, args.concurrency)
    if command == "generate":
        return generate_tools.generate_image_free(
            args.prompt, args.width, args.height, args.seed, out, ow
        )
    raise AssertionError(f"unhandled command {command!r}")  # pragma: no cover


def _scalar(value: object) -> str:
    return json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value)


def _nested(value: object, indent: int) -> list[str]:
    """Indented lines for a nested dict/list; one fact per line, no JSON blob."""
    pad = " " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)) and item and not (
                isinstance(item, list) and all(not isinstance(i, (dict, list)) for i in item)
            ):
                lines.append(f"{pad}{key}:")
                lines.extend(_nested(item, indent + 2))
            elif isinstance(item, list):
                lines.append(f"{pad}{key}: {', '.join(_scalar(i) for i in item) or '-'}")
            else:
                lines.append(f"{pad}{key}: {_scalar(item)}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                inner = _nested(item, indent + 2)
                inner[0] = f"{pad}- " + inner[0].lstrip()
                lines.extend(inner)
            else:
                lines.append(f"{pad}- {_scalar(item)}")
    return lines


def _table(rows: list[list[str]]) -> list[str]:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return ["  " + "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip() for row in rows]


def _render_special(result: dict) -> list[str] | None:
    """Readable text for the three listing commands; None for everything else."""
    op = result.get("operation")
    if op == "list_capabilities":
        tools = result["tools"]
        ready = sum(1 for t in tools if t["ready"])
        hosted = sum(1 for t in tools if t["execution"] == "hosted")
        rows = [["tool", "ready", "network", "needs"]]
        blocked: list[str] = []
        for t in tools:
            needs = []
            if t["gpu"] != "none":
                needs.append(f"gpu {t['gpu']}")
            needs += t["external_binaries"] + [f"{b} (some inputs)" for b in t["conditional_binaries"]]
            if t["external_service"]:
                needs.append(t["external_service"])
            rows.append([t["tool"], "yes" if t["ready"] else "NO", t["network"], ", ".join(needs) or "-"])
            blocked += [f"  blocked  {t['tool']}: {b}" for b in t["blockers"]]
            blocked += [f"  limited  {t['tool']}: {b}" for b in t["limitations"]]
        lines = [f"{len(tools)} tools: {len(tools) - hosted} local, {hosted} hosted; {ready} ready on this machine", ""]
        lines += _table(rows)
        if blocked:
            lines += [""] + blocked
        lines += ["", "  environment:"] + _nested(result["environment"], 4)
        lines += ["", "  limits:"] + _nested(result["limits"], 4)
        lines += [""] + [f"  note: {n}" for n in result.get("notes", [])]
        return lines
    if op == "list_background_models":
        rows = [["model", "weights", "licence", "verified"]]
        for m in result["models"]:
            weights = f"{m['weights_mb']} MB" if m.get("weights_mb") else "?"
            rows.append([m["model"], weights, m["license"], "yes" if m["license_verified"] else "NO"])
        lines = [f"default model: {result['default']}", ""] + _table(rows)
        return lines + [""] + [f"  note: {n}" for n in result.get("notes", [])]
    if op == "list_presets":
        rows = [["kind", "name", "size"]]
        for kind in ("image", "video"):
            for name, size in result[kind].items():
                rows.append([kind, name, f"{size['width']}x{size['height']}"])
        return _table(rows) + ["", f"  {result['disclaimer']}", f"  {result['override']}"]
    return None


def _render(result: object, as_json: bool) -> str:
    if as_json or not isinstance(result, dict):
        return json.dumps(result, indent=2, default=str) if not isinstance(result, str) else result
    special = _render_special(result)
    if special is not None:
        return "\n".join(["  execution: local", "  network: none", ""] + special)
    lines = []
    if "output_path" in result:
        lines.append(str(result["output_path"]))
    for key, value in result.items():
        if key in ("operation", "output_path"):
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            lines.append(f"  {key}: {', '.join(value)}")
        elif isinstance(value, (dict, list)):
            lines.append(f"  {key}:")
            lines.extend(_nested(value, 4))
        else:
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return EXIT_USAGE

    configure(args.log_level)
    if args.log_level or args.output_dir:
        base = get_config()
        overrides = {}
        if args.log_level:
            overrides["log_level"] = args.log_level
        if args.output_dir:
            from pathlib import Path

            overrides["output_dir"] = Path(args.output_dir).expanduser()
        set_config(Config(**{**base.__dict__, **overrides}))

    if args.command == "serve":
        from .server import main as serve

        serve()
        return EXIT_OK

    try:
        result = _dispatch(args)
    except ToolkitError as exc:
        verbose = (args.log_level or get_config().log_level) == "verbose"
        print(f"mct: {exc.describe(verbose)}", file=sys.stderr)
        return EXIT_TOOL_ERROR
    except KeyboardInterrupt:  # pragma: no cover
        print("mct: interrupted", file=sys.stderr)
        return EXIT_TOOL_ERROR

    print(_render(result, args.json))
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
