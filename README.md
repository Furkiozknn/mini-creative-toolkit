![mini-creative-toolkit](assets/banner.svg)

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-8effc2?style=flat-square" alt="license: MIT">
  <img src="https://img.shields.io/badge/python-3.11%2B-ffd76d?style=flat-square" alt="python 3.11+">
  <img src="https://img.shields.io/badge/protocol-MCP-ff9f5a?style=flat-square" alt="MCP protocol">
  <img src="https://github.com/Furkiozknn/mini-creative-toolkit/actions/workflows/ci.yml/badge.svg" alt="tests">
  <img src="https://img.shields.io/badge/paid%20APIs-0-8effc2?style=flat-square" alt="0 paid APIs">
  <img src="https://img.shields.io/badge/hosted%20tools-1%20of%2023-ff9f5a?style=flat-square" alt="1 of 23 tools is hosted">
</p>

<p align="center"><b>Local media operations for MCP clients. Images, video and audio.</b><br>
CPU-first. No paid APIs. External network access is isolated to one tool and explicitly documented.</p>

---

## Contents

- [Why this exists](#why-this-exists)
- [What it does](#what-it-does)
- [Capability matrix](#capability-matrix)
- [Install](#install)
- [Register as an MCP server](#register-as-an-mcp-server)
- [CLI](#cli)
- [Batch processing](#batch-processing)
- [Configuration](#configuration)
- [Supported formats](#supported-formats)
- [Security model](#security-model)
- [Architecture](#architecture)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)
- [Licensing](#licensing)

---

## Why this exists

Removing a background, fitting an image to 1080×1080, converting a folder to
WebP, pulling three seconds out of a clip as a GIF, stripping GPS coordinates
before you share a photo — **none of this needs a model, and none of it needs
somebody else's paid API.** It is mechanical work, and it finishes on a
laptop CPU in about the time it takes to read this sentence.

The interesting property of this project is not that it uses AI. It is how
little of it needs to.

Of 23 tools, **22 run entirely on this machine**. One — `generate_image_free`
— genuinely generates an image, so it genuinely has to call a hosted service,
and it says so in its own tool description, in its result payload, in the
capability matrix below, and in `SECURITY.md`. That tool lives alone in one
file, and a test asserts that no other module imports an HTTP client.

There is no global "CPU-only, no network" claim anywhere in this project,
because two of its tools would make such a claim false. Requirements are
declared per tool, in one table, from which both the MCP descriptions and the
matrix below are generated.

---

## What it does

Give an MCP client something like:

> "Remove the background from this, make it 1080×1080 without cropping the
> subject, strip the metadata, and optimise it for the web."

and it has a tool for each step. Or ask it to inspect something first —
`inspect_media` reports what a file actually is rather than what its
extension claims — and decide from there.

### Discovery

| Tool | Does |
| --- | --- |
| `list_capabilities` | Every tool's requirements **and whether this machine can currently run it** |
| `inspect_media` | Format, dimensions, codecs, duration, fps, metadata presence |
| `list_background_models` | rembg models with size, speed, and licence status |
| `list_presets` | Built-in dimension presets |

### Images

| Tool | Does |
| --- | --- |
| `resize_image` | Lanczos resize; fits inside the box without distorting by default |
| `convert_format` | PNG / JPEG / WebP / AVIF, with quality and lossless controls |
| `strip_metadata` | Rebuilds from raw pixels — EXIF, GPS, ICC, XMP, PNG text chunks all gone |
| `add_watermark` | Semi-transparent text at a corner or the centre |
| `remove_background` | Subject cut-out to a transparent PNG |
| `create_contact_sheet` | Tile many images into one review sheet |
| `compare_images` | Byte equality, dimensions, and a coarse similarity score |

### Upscaling

| Tool | Does |
| --- | --- |
| `upscale_image_fast` | FSRCNN — a real super-resolution CNN, CPU, sub-second |
| `upscale_image` | Real-ESRGAN via Upscayl — best quality, **needs a discrete GPU** |
| `upscale_image_auto` | Picks between them and **explains which and why** |

### Video and audio

| Tool | Does |
| --- | --- |
| `video_thumbnail` | One frame as a PNG |
| `video_to_gif` | Two-pass palette GIF, with frame-count guards |
| `video_trim` | Lossless stream copy, re-encoding only when the copy lands short |
| `video_resize` | Scale, always to even dimensions (H.264 requires them) |
| `video_compress` | H.264/AAC at a chosen CRF |
| `extract_audio` | mp3 or wav |

### Higher-level

| Tool | Does |
| --- | --- |
| `optimize_media` | Inspect → choose a pipeline → apply → **report every trade made** |
| `batch_process` | One operation over many files, bounded concurrency, failure isolated |

### Hosted — the one that leaves your machine

| Tool | Does |
| --- | --- |
| `generate_image_free` | Text → image via Pollinations.ai. **Your prompt is sent to a third party.** |

---

## Capability matrix

Generated from the same table the MCP tool descriptions use — run
`mct capabilities` for the live version, including what this machine is
actually missing.

| Tool | Local | Network | GPU | External binary | Deterministic |
| --- | :---: | :---: | :---: | :---: | :---: |
| `resize_image` | yes | no | no | no | yes |
| `convert_format` | yes | no | no | no | yes |
| `strip_metadata` | yes | no | no | no | yes |
| `add_watermark` | yes | no | no | no | yes |
| `create_contact_sheet` | yes | no | no | no | yes |
| `compare_images` | yes | no | no | no | yes |
| `remove_background` | yes | first run only | optional | no | per model |
| `upscale_image_fast` | yes | no | no | no | yes |
| `upscale_image` | yes | no | **required** | `upscayl-bin` | yes |
| `upscale_image_auto` | yes | no | optional | only if selected | yes |
| `video_thumbnail` | yes | no | no | `ffmpeg` | yes |
| `video_to_gif` | yes | no | no | `ffmpeg` | yes |
| `video_trim` | yes | no | no | `ffmpeg`, `ffprobe` | yes |
| `video_resize` | yes | no | no | `ffmpeg`, `ffprobe` | yes |
| `video_compress` | yes | no | no | `ffmpeg`, `ffprobe` | yes |
| `extract_audio` | yes | no | no | `ffmpeg` | yes |
| `inspect_media` | yes | no | no | `ffprobe` (AV only) | yes |
| `optimize_media` | yes | no | no | `ffmpeg` (video only) | yes |
| `batch_process` | yes | no | no | per operation | yes |
| `list_capabilities` | yes | no | no | no | yes |
| `list_background_models` | yes | no | no | no | yes |
| `list_presets` | yes | no | no | no | yes |
| `generate_image_free` | **no** | **required** | no | no | **no** |

"first run only" is not a hedge: rembg downloads a model's ONNX weights the
first time that model is used, then never again. "per model" means
`remove_background` is reproducible for a given model but different models
give different cut-outs.

`mct capabilities` distinguishes two kinds of unmet requirement, because
conflating them sends you looking for a problem you do not have:

- **blockers** — the tool cannot run at all. `video_thumbnail` without ffmpeg.
- **limitations** — the tool runs, on fewer inputs. `inspect_media` without
  ffprobe still describes every image; it just cannot open a video.

---

## Install

```bash
uv sync
```

That installs the package and its five dependencies. The FSRCNN weights
(~120 KB total) ship inside the package — nothing to download.

**ffmpeg and ffprobe must be on your PATH** for every video and audio tool,
and for `inspect_media` on non-image files:

```bash
sudo apt-get install ffmpeg     # Debian/Ubuntu
brew install ffmpeg             # macOS
```

Everything else works without them. `mct capabilities` will tell you exactly
which tools are blocked and why.

### Optional: Real-ESRGAN upscaling

`upscale_image` reuses a local [Upscayl](https://github.com/upscayl/upscayl)
install. Nothing is bundled and nothing is downloaded — point two environment
variables at your own copy:

```bash
export UPSCAYL_BIN_PATH=/path/to/upscayl/resources/linux/bin/upscayl-bin
export UPSCAYL_MODELS_PATH=/path/to/upscayl/resources/models
```

If they are unset or wrong, `upscale_image` raises a clear error naming both
variables — and every other tool keeps working. Skip this entirely and use
`upscale_image_fast`, which needs no setup at all.

---

## Register as an MCP server

```bash
claude mcp add --transport stdio mini-creative-toolkit -- uv run --project /path/to/this/repo toolkit.py
```

`toolkit.py` is preserved as a compatibility launcher, so existing
configurations need no change. The modern equivalents:

```bash
mct serve
python -m mini_creative_toolkit
```

---

## CLI

The CLI calls the same functions the MCP server does — there is no second
implementation of any rule.

```bash
mct inspect photo.jpg
mct resize photo.jpg --width 1080 --height 1080
mct convert photo.png --format webp --quality 85
mct optimize photo.png --goal web
mct optimize photo.png --goal social --preset square
mct strip-metadata photo.jpg
mct watermark photo.jpg --text "© 2026" --position bottom-right --opacity 0.4
mct remove-bg photo.jpg
mct upscale icon.png --scale 4              # picks a method and explains it
mct thumbnail clip.mp4 --at 00:00:05
mct gif clip.mp4 --start 00:00:02 --duration 3 --fps 12 --width 480
mct trim clip.mp4 --start 00:00:10 --duration 15
mct compress clip.mp4 --crf 26
mct audio clip.mp4 --format mp3
mct contact-sheet renders/*.png --columns 4
mct compare a.png b.png
mct capabilities
mct presets
mct models
```

Add `--json` for machine-readable output, `--log-level verbose` to see the
underlying ffmpeg log when something fails, `-o PATH` to choose a destination
(`--overwrite` to allow replacing an existing file).

Exit codes: `0` success, `1` operation failed, `2` usage error.

---

## Batch processing

```bash
mct batch photos/*.jpg --operation optimize --options '{"goal":"web"}'
mct batch renders/*.png --operation resize --options '{"width":1080,"height":1080}'
```

or as an MCP call:

```json
{
  "paths": ["a.png", "b.png", "c.png"],
  "operation": "convert_format",
  "options": {"target_format": "webp", "quality": 85}
}
```

returning

```json
{"total": 3, "succeeded": 2, "failed": 1, "results": [...], "errors": [...]}
```

Three properties are enforced, not hoped for:

- **One bad file never loses the batch.** Each item runs in its own
  try/except; failures land in `errors` with their original index.
- **Concurrency is bounded and conservative.** CPU-heavy operations
  (`remove_background`, `upscale_fast`) get a lower cap than cheap ones —
  saturating every core with ONNX sessions makes a batch of 20 slower than
  doing them one at a time.
- **Outputs cannot collide.** Generated names carry random bytes as well as a
  timestamp, and passing an explicit `output_path` to a batch is refused
  rather than silently ignored.

---

## Configuration

Nothing is required. Every variable exists to tighten a default or raise a
limit your real workload legitimately exceeds.

| Variable | Default | Meaning |
| --- | --- | --- |
| `MCT_OUTPUT_DIR` | `output/` | Where generated files land |
| `MCT_ALLOWED_ROOTS` | *(unset)* | Restrict file access to these directories |
| `MCT_MAX_INPUT_MB` | 512 | Largest input file |
| `MCT_MAX_OUTPUT_MB` | 1024 | Largest output file |
| `MCT_MAX_IMAGE_PIXELS` | 80000000 | Decompression-bomb guard |
| `MCT_MAX_VIDEO_DURATION` | 3600 | Longest video, in seconds |
| `MCT_MAX_VIDEO_WIDTH` / `_HEIGHT` | 7680 | Largest video dimensions |
| `MCT_MAX_BATCH_ITEMS` | 200 | Largest batch |
| `MCT_BATCH_CONCURRENCY` | 4 | Workers for standard operations |
| `MCT_HEAVY_BATCH_CONCURRENCY` | 2 | Workers for CPU-heavy operations |
| `MCT_HTTP_TIMEOUT` | 60 | Hosted call timeout, in seconds |
| `MCT_MAX_DOWNLOAD_MB` | 64 | Largest hosted response |
| `MCT_SUBPROCESS_TIMEOUT` | 900 | ffmpeg / Upscayl timeout, in seconds |
| `MCT_LOG_LEVEL` | `normal` | `quiet`, `normal` or `verbose` |
| `MCT_LEGACY_STRING_RESULTS` | `false` | Return a bare path string, as before 2.0 |
| `MCT_PRESETS_IMAGE_<NAME>` | — | Override a preset, e.g. `1200x1200` |
| `UPSCAYL_BIN_PATH` / `UPSCAYL_MODELS_PATH` | *(unset)* | Local Upscayl install |

A bad value fails loudly at startup with a message naming the variable, and
every resource-limit error names the limit it hit.

---

## Supported formats

**Images, read:** everything Pillow reads.
**Images, written:** PNG, JPEG, WebP, and AVIF *if your Pillow build has it* —
support is probed at runtime rather than assumed, because AVIF depends on how
Pillow was compiled. `mct capabilities` reports what this install can write.

**Video and audio:** whatever your ffmpeg build handles. `video_resize` and
`video_compress` output H.264/AAC in MP4; `extract_audio` writes mp3 or wav.

---

## Security model

Full detail in [`SECURITY.md`](SECURITY.md). The short version:

> **This project is a local media-processing tool, not a sandbox.**

It runs as your user with your user's permissions, and MCP does not change
that. What it *does* guarantee:

- **No `shell=True` anywhere.** A test parses the AST of every module to
  enforce it. Commands are argument lists; binaries come from `shutil.which`.
- **Every non-path value that reaches `argv` is shape-constrained.**
  Timestamps must match a digits-and-colons grammar much narrower than
  ffmpeg's own, so a value like `-ss` or `-i` cannot be read as an option.
  Rejected, never sanitised.
- **Paths are resolved before they are checked.** `resolve()` collapses `..`
  and follows symlinks first, so neither traversal nor a planted symlink can
  escape a configured allowed root.
- **Nothing overwrites your input.** Writes are staged to a temporary sibling
  and renamed into place only on success, so a crashed ffmpeg leaves no
  truncated file and no orphaned GIF palette.
- **The hosted response is never trusted.** Status, content type, a streaming
  byte budget, and an actual decode — an HTML error page served with HTTP 200
  is refused rather than written out as a `.jpg`.

If you are exposing this to a model you do not fully trust, set
`MCT_ALLOWED_ROOTS`. It is unset by default, and `SECURITY.md` says so
plainly rather than implying an isolation that does not exist.

---

## Architecture

```
src/mini_creative_toolkit/
├── config.py         MCT_* settings, limits, allowed roots
├── errors.py         domain errors; MCP-facing message vs verbose detail
├── validation.py     everything that reaches an argv entry passes through here
├── paths.py          untrusted-path resolution + staged output manager
├── capabilities.py   one table: requirements, readiness, description footers
├── media_info.py     the engine behind inspect_media
├── results.py        structured result shape
├── log.py            stderr, three levels, never logs secrets or prompts
├── engines/          ffmpeg · images (Pillow+OpenCV) · background · upscayl · pollinations
├── tools/            the business rules — MCP and CLI both call these
├── server.py         MCP registration and descriptions, no logic
├── cli.py            mct — same functions, different surface
└── models/           bundled FSRCNN weights
```

Two rules hold the shape:

1. **Business logic exists once.** `server.py` and `cli.py` both call
   `tools/`. A validation fix lands in both surfaces at the same moment.
2. **Capabilities are declared once.** Tool descriptions, the readiness
   report, and the matrix above all read the same table, so a description
   cannot drift away from what the tool actually needs.

---

## Testing

```bash
uv run pytest
```

Real files, real ffmpeg, real encoders — no mocked image libraries. The
exception is the hosted generator, which is tested entirely against an
`httpx.MockTransport`: **CI never contacts Pollinations.ai**, and a test suite
that quietly started making outbound requests would contradict the project's
central claim.

The suite covers unit tests for validation, path handling and configuration;
end-to-end image and video tests; security tests for traversal, symlink
escapes, shell metacharacters, unicode and awkward filenames, FIFOs, NUL
bytes, over-long paths and every resource limit; failure-mode tests for the
hosted engine (timeout, 4xx, 5xx, wrong content type, corrupt body, oversized
response); batch failure isolation; a real MCP stdio handshake; and static
checks over the repository itself — no `shell=True`, no developer-specific
paths, no outbound URL outside the hosted engine.

---

## Troubleshooting

**"ffmpeg was not found on PATH"** — install it; the error names the command
for your platform. Image tools are unaffected.

**`upscale_image` fails with "UPSCAYL_BIN_PATH is not set"** — expected if you
have not installed Upscayl. Use `upscale_image_fast` or `upscale_image_auto`.

**An operation says a limit was exceeded** — the message names the variable
and its current value. Raise it if the file is legitimate.

**AVIF conversion fails** — your Pillow build has no AVIF encoder. Run
`mct capabilities` to see what it can write.

**A GIF request is refused for frame count** — `fps × duration` was too high.
GIF is a poor format above a few hundred frames; lower one of them.

**Something failed and the message is short** — that is deliberate. Re-run
with `MCT_LOG_LEVEL=verbose` or `--log-level verbose` for the underlying log.

**Files appear in an unexpected place** — set `MCT_OUTPUT_DIR`. The default is
`output/` inside the repository, preserved from before 2.0.

---

## Limitations

Stated rather than hidden:

- **`upscale_image` needs a discrete GPU.** Measured on Intel integrated
  graphics: a single small icon reached 32% after seven minutes and did not
  finish. This is not a bug and it is not being fixed — Vulkan-based
  Real-ESRGAN needs real hardware. `upscale_image_auto` will not select it
  unless a discrete GPU is detected.
- **FSRCNN is not Real-ESRGAN.** It sharpens edges; it does not invent
  texture. Nothing in this project claims otherwise.
- **`compare_images` is not forensic.** The similarity score is an average
  channel difference on 64×64 thumbnails. It is a "same picture?" hint, not
  evidence.
- **Presets are a convenience, not a certification.** No platform's current
  requirements are encoded here and platform requirements change.
- **`generate_image_free` depends on a free public service** with no
  availability or privacy guarantee. If it changes or disappears, nothing
  else here is affected.
- **Model licences are not all verified.** Where one was not confirmed
  against a primary source, `list_background_models` says `not verified`
  rather than guessing.
- **This is not a sandbox.** See [`SECURITY.md`](SECURITY.md).

---

## Licensing

This repository is **MIT**. That covers this project's code and nothing else.

Model weights, external binaries and dependencies carry their own terms — and
one commonly-reachable rembg model is **non-commercial**. See
[`THIRD_PARTY.md`](THIRD_PARTY.md) before assuming MIT applies to what a tool
hands you.
