"""What each tool actually requires, declared once and reused everywhere.

This exists because the old README made a global claim - "CPU-only, no
network" - that one tool (``upscale_image``) and one other tool
(``generate_image_free``) both broke. A single global claim about a server
with heterogeneous tools is always going to be wrong about something. So the
claim lives per tool instead, and both the MCP tool descriptions and the
README capability matrix are generated from this one table.

A capability declared here is a *static* property of the tool. Whether the
requirement is currently *satisfied* on this machine is a separate question,
answered at runtime by :func:`probe_environment`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .config import Config, get_config


class ExecutionMode(str, Enum):
    LOCAL = "local"
    HOSTED = "hosted"


class GpuNeed(str, Enum):
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"


class NetworkNeed(str, Enum):
    NONE = "none"
    #: No network at steady state, but a first run may download model weights.
    FIRST_RUN_ONLY = "first-run-only"
    REQUIRED = "required"


@dataclass(frozen=True)
class ToolCapability:
    name: str
    summary: str
    execution: ExecutionMode = ExecutionMode.LOCAL
    network: NetworkNeed = NetworkNeed.NONE
    gpu: GpuNeed = GpuNeed.NONE
    #: Binaries this tool always needs.
    external_binaries: tuple[str, ...] = ()
    #: Binaries needed only for *some* inputs. `inspect_media` needs ffprobe
    #: for video and audio but not for images, so calling it "not ready" when
    #: ffmpeg is absent would be a broader claim than the truth.
    conditional_binaries: tuple[str, ...] = ()
    external_service: str | None = None
    model: str | None = None
    reads_files: bool = True
    writes_files: bool = True
    uses_subprocess: bool = False
    potentially_slow: bool = False
    #: True when the same input always yields byte-identical output modulo the
    #: timestamped filename. False for anything involving a generative model.
    deterministic: bool = True
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "tool": self.name,
            "summary": self.summary,
            "execution": self.execution.value,
            "network": self.network.value,
            "gpu": self.gpu.value,
            "external_binaries": list(self.external_binaries),
            "conditional_binaries": list(self.conditional_binaries),
            "external_service": self.external_service,
            "model": self.model,
            "reads_files": self.reads_files,
            "writes_files": self.writes_files,
            "uses_subprocess": self.uses_subprocess,
            "potentially_slow": self.potentially_slow,
            "deterministic": self.deterministic,
            "notes": list(self.notes),
        }

    def description_footer(self) -> str:
        """The capability disclosure appended to every MCP tool docstring."""
        parts = [f"execution: {self.execution.value}", f"network: {self.network.value}"]
        if self.gpu is not GpuNeed.NONE:
            parts.append(f"gpu: {self.gpu.value}")
        if self.external_binaries:
            parts.append(f"requires binary: {', '.join(self.external_binaries)}")
        if self.conditional_binaries:
            parts.append(f"needs for some inputs: {', '.join(self.conditional_binaries)}")
        if self.external_service:
            parts.append(f"external service: {self.external_service}")
        if self.model:
            parts.append(f"model: {self.model}")
        if self.potentially_slow:
            parts.append("may be slow")
        if not self.deterministic:
            parts.append("non-deterministic")
        return " | ".join(parts)


def _cap(name: str, summary: str, **kwargs) -> ToolCapability:
    return ToolCapability(name=name, summary=summary, **kwargs)


FFMPEG = ("ffmpeg",)
FFPROBE = ("ffprobe",)
FFMPEG_PROBE = ("ffmpeg", "ffprobe")

CAPABILITIES: dict[str, ToolCapability] = {
    c.name: c
    for c in [
        _cap("resize_image", "Lanczos resize/fit with Pillow."),
        _cap("convert_format", "Re-encode an image to PNG/JPEG/WebP (AVIF when supported)."),
        _cap("strip_metadata", "Rebuild an image from raw pixels, dropping all metadata."),
        _cap("add_watermark", "Draw semi-transparent text onto an image."),
        _cap(
            "remove_background",
            "Cut the subject out of an image into a transparent PNG.",
            network=NetworkNeed.FIRST_RUN_ONLY,
            gpu=GpuNeed.OPTIONAL,
            model="u2net (default)",
            potentially_slow=True,
            deterministic=False,
            notes=(
                "rembg downloads the ONNX weights on first use for a model it has not "
                "cached yet; after that it is fully offline.",
                "Output depends on the chosen model, so results are reproducible per "
                "model but not identical across models.",
            ),
        ),
        _cap(
            "upscale_image_fast",
            "FSRCNN super-resolution (OpenCV dnn_superres), CPU, sub-second.",
            model="FSRCNN x2/x3/x4 (bundled)",
        ),
        _cap(
            "upscale_image",
            "Real-ESRGAN super-resolution via Upscayl's Vulkan binary.",
            gpu=GpuNeed.REQUIRED,
            external_binaries=("upscayl-bin",),
            model="Upscayl model set (not bundled)",
            potentially_slow=True,
            notes=(
                "Needs a discrete GPU. On integrated graphics a single small icon "
                "was measured at over seven minutes without finishing.",
                "Requires UPSCAYL_BIN_PATH and UPSCAYL_MODELS_PATH.",
            ),
        ),
        _cap(
            "upscale_image_auto",
            "Pick the best available upscaler for this machine and explain the choice.",
            gpu=GpuNeed.OPTIONAL,
            external_binaries=("upscayl-bin (only if selected)",),
            potentially_slow=True,
            notes=("Falls back to FSRCNN, then Lanczos, and always reports which ran.",),
        ),
        _cap("video_thumbnail", "Grab one frame from a video as a PNG.", external_binaries=FFMPEG, uses_subprocess=True),
        _cap("video_to_gif", "Two-pass palette GIF from a video clip.", external_binaries=FFMPEG, uses_subprocess=True, potentially_slow=True),
        _cap("video_trim", "Cut a clip, stream-copy first, re-encode only if needed.", external_binaries=FFMPEG_PROBE, uses_subprocess=True),
        _cap("video_resize", "Scale a video, preserving aspect ratio by default.", external_binaries=FFMPEG_PROBE, uses_subprocess=True, potentially_slow=True),
        _cap("video_compress", "Re-encode to H.264/AAC at a chosen CRF.", external_binaries=FFMPEG_PROBE, uses_subprocess=True, potentially_slow=True),
        _cap("extract_audio", "Pull the audio track out as mp3 or wav.", external_binaries=FFMPEG, uses_subprocess=True),
        _cap(
            "inspect_media",
            "Report format, dimensions, codecs, duration, metadata presence.",
            conditional_binaries=("ffprobe",), uses_subprocess=True, writes_files=False,
            notes=("Images need nothing beyond Pillow; ffprobe is only required for "
                   "video and audio files.",),
        ),
        _cap(
            "optimize_media",
            "Inspect, then choose and apply a deterministic optimisation.",
            conditional_binaries=("ffmpeg", "ffprobe"), uses_subprocess=True, potentially_slow=True,
            notes=("Images are handled entirely by Pillow; ffmpeg is only required "
                   "when the input is a video.",),
        ),
        _cap("create_contact_sheet", "Tile several images into one review sheet."),
        _cap("compare_images", "Compare two images: size, bytes, and a difference score.", writes_files=False),
        _cap("batch_process", "Apply one operation to many files with bounded concurrency.", potentially_slow=True),
        _cap("list_capabilities", "Describe every tool's requirements and this machine's readiness.", reads_files=False, writes_files=False),
        _cap("list_background_models", "List rembg models with their characteristics and licence status.", reads_files=False, writes_files=False),
        _cap("list_presets", "List the built-in social image/video dimension presets.", reads_files=False, writes_files=False),
        _cap(
            "generate_image_free",
            "Text-to-image via the Pollinations.ai public endpoint.",
            execution=ExecutionMode.HOSTED,
            network=NetworkNeed.REQUIRED,
            external_service="Pollinations.ai",
            reads_files=False,
            deterministic=False,
            potentially_slow=True,
            notes=(
                "This is the only tool that leaves the machine. Your prompt text is "
                "sent to a third party.",
                "No API key is required today. That is a property of the service, not "
                "a guarantee - it may change without notice.",
            ),
        ),
    ]
}


def _which(name: str) -> str | None:
    return shutil.which(name)


def _detect_discrete_gpu() -> tuple[bool, str]:
    """Best-effort discrete-GPU detection. Never raises, never blocks long.

    This decides only which *upscaler* gets picked automatically, so being
    wrong is a performance choice, not a correctness one - and the tool that
    uses it always reports what it selected and why.
    """
    if os.environ.get("MCT_FORCE_GPU", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True, "MCT_FORCE_GPU is set"
    if os.environ.get("MCT_FORCE_NO_GPU", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False, "MCT_FORCE_NO_GPU is set"

    nvidia = _which("nvidia-smi")
    if nvidia:
        try:
            proc = subprocess.run(
                [nvidia, "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            names = [n.strip() for n in proc.stdout.splitlines() if n.strip()]
            if proc.returncode == 0 and names:
                return True, f"nvidia-smi reports {names[0]}"
        except (OSError, subprocess.SubprocessError):
            pass

    # Linux: a discrete card shows up as its own DRM node with a vendor that
    # is not Intel's integrated graphics. This is a heuristic and is labelled
    # as one in the result the caller sees.
    drm = Path("/sys/class/drm")
    if drm.is_dir():
        for card in sorted(drm.glob("card[0-9]*")):
            vendor_file = card / "device" / "vendor"
            try:
                vendor = vendor_file.read_text().strip().lower()
            except OSError:
                continue
            if vendor in {"0x10de", "0x1002"}:  # NVIDIA, AMD
                return True, f"DRM device {card.name} has a discrete-GPU vendor id ({vendor})"
    return False, "no discrete GPU detected (checked nvidia-smi and /sys/class/drm)"


def probe_environment(config: Config | None = None) -> dict:
    """What this specific machine can actually do, right now."""
    config = config or get_config()
    has_gpu, gpu_reason = _detect_discrete_gpu()

    upscayl_bin = config.upscayl_bin
    upscayl_models = config.upscayl_models
    fsrcnn_dir = Path(__file__).resolve().parent / "models"

    formats = _pillow_formats()
    return {
        "ffmpeg": _which("ffmpeg"),
        "ffprobe": _which("ffprobe"),
        "discrete_gpu": has_gpu,
        "discrete_gpu_reason": gpu_reason,
        "upscayl_bin": str(upscayl_bin) if upscayl_bin else None,
        "upscayl_bin_present": bool(upscayl_bin and upscayl_bin.is_file()),
        "upscayl_models": str(upscayl_models) if upscayl_models else None,
        "upscayl_models_present": bool(upscayl_models and upscayl_models.is_dir()),
        "fsrcnn_models_present": sorted(p.name for p in fsrcnn_dir.glob("FSRCNN_x*.pb")),
        "image_write_formats": formats,
    }


def _pillow_formats() -> dict:
    """Which encoders this Pillow build actually has.

    Checked at runtime rather than assumed: WebP is near-universal but AVIF
    depends on how Pillow was built, and claiming support this install does
    not have would turn a clear error into a confusing one.
    """
    try:
        from PIL import Image, features
    except Exception:  # pragma: no cover - Pillow is a hard dependency
        return {}
    Image.init()
    result = {}
    for fmt, feature in (("PNG", None), ("JPEG", None), ("WEBP", "webp"), ("AVIF", "avif")):
        if feature is not None:
            try:
                supported = bool(features.check(feature))
            except ValueError:
                supported = False
        else:
            supported = fmt in Image.SAVE
        result[fmt.lower()] = supported and fmt in Image.SAVE
    return result


def readiness(config: Config | None = None) -> dict:
    """Per-tool: is every requirement met on this machine?"""
    config = config or get_config()
    env = probe_environment(config)
    out = {}
    for name, cap in CAPABILITIES.items():
        blockers = []
        # Things the tool cannot work at all without.
        if "ffmpeg" in cap.external_binaries and not env["ffmpeg"]:
            blockers.append("ffmpeg is not on PATH")
        if "ffprobe" in cap.external_binaries and not env["ffprobe"]:
            blockers.append("ffprobe is not on PATH")

        # Things that narrow what it can accept, without stopping it. Reporting
        # these as blockers would tell a caller that inspect_media is
        # unavailable when it still handles every image fine.
        limitations = []
        if "ffmpeg" in cap.conditional_binaries and not env["ffmpeg"]:
            limitations.append("ffmpeg is not on PATH, so video inputs are unavailable")
        if "ffprobe" in cap.conditional_binaries and not env["ffprobe"]:
            limitations.append(
                "ffprobe is not on PATH, so video and audio inputs are unavailable"
            )

        if name == "upscale_image":
            if not env["upscayl_bin_present"]:
                blockers.append("UPSCAYL_BIN_PATH is unset or does not point at a file")
            if not env["upscayl_models_present"]:
                blockers.append("UPSCAYL_MODELS_PATH is unset or does not point at a directory")
            if not env["discrete_gpu"]:
                blockers.append("no discrete GPU detected - this would be impractically slow")
        if name == "upscale_image_fast" and not env["fsrcnn_models_present"]:
            blockers.append("bundled FSRCNN weights are missing from the package")
        out[name] = {"ready": not blockers, "blockers": blockers, "limitations": limitations}
    return out
