# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> This file was reconstructed from the repository's own history. The project
> carries no release tags, so each version below is dated by the commit that
> set it in `pyproject.toml`, and anything merged after the `2.0.0` bump is
> listed under *Unreleased* rather than backdated into a release it may not
> have shipped in. Entries cover user-visible changes only; where the history
> does not establish a change, nothing is claimed for it.

## [Unreleased]

### Added

- Model reuse across calls: `rembg` sessions are cached per model name and
  FSRCNN networks per scale, for the life of the process. `MCT_CACHE_MODELS=0`
  opts out on a host that cannot spare the memory.

- A `mini-creative-toolkit` console script that starts the stdio server. It is
  what `uvx mini-creative-toolkit` - the launch command `server.json` hands to
  MCP Registry clients - looks for; before it, the registry entry installed and
  then failed with "executable not provided".

### Fixed

- `MCT_ALLOWED_ROOTS` could be sidestepped with a playlist: an HLS `.m3u8`
  inside an allowed root makes ffmpeg open the segments it lists, wherever they
  are. Inputs that ffprobe identifies as a playlist or manifest (`hls`, `dash`,
  `concat`, `imf`) are now refused with an `InvalidInputError`.
- An explicit `output_path` containing `%` (for example `frame%03d.png`) made
  ffmpeg's image muxer write a differently named, never-cleaned-up
  `frame1.part-*.png` and the tool then report "wrote no output". The staging
  name is now filename-safe; the final name is still exactly the one asked for.
- "22 of 23 tools report `network: none`" was one too many: `remove_background`
  reports `first-run-only`, because rembg downloads its weights on first use.
  `server.json`, the README, the project metadata and two diagrams now say 21,
  and a test ties that number to the capability table.
- `batch_process` still printed `"network": "none"` when its operation was
  `remove_background`, which downloads rembg weights on first use (seen with a
  clean `U2NET_HOME`: the batch fetched `u2netp.onnx` from GitHub and reported
  `none`). The payload now reports the network need of the operation that ran,
  and the capability table marks `batch_process` `first-run-only`, so the
  published count is 20, not 21. A test now checks every README matrix row's
  Network cell against the table, not just that the tool is mentioned.
- The default output directory no longer assumes a source checkout. Installed
  non-editably, `output/` is resolved under the current working directory
  instead of inside the interpreter's own tree.
- The one outbound network path no longer follows redirects to arbitrary
  origins: a `3xx` is resolved and its target checked against the service's own
  hosts before the next request is made.
- README: the two routing diagrams that had gone stale were corrected.

## [2.0.0] - 2026-09-04

Breaking release. The single-file `toolkit.py` became the packaged
`mini_creative_toolkit`, with a shared tools layer behind both the MCP server
and a new `mct` CLI.

### Added

- `mct` command-line interface, and `python -m mini_creative_toolkit`.
- Eleven further tools, for twenty-three in total; capabilities are declared
  once and drive tool descriptions, readiness reporting and the README matrix.
- `MCT_LEGACY_STRING_RESULTS=1`, which restores the pre-2.0 return shape
  verbatim for callers that need it.
- `SECURITY.md` and `THIRD_PARTY.md`.

### Changed

- **Breaking:** every tool returns a structured dict instead of a bare path
  string. `output_path` carries exactly what the old return value carried, so a
  caller reading only that key keeps working.
- Hardening: no `shell=True` (enforced by an AST check), argument-injection
  guards on every argv value, resolve-before-check path handling, staged
  writes, validated hosted responses, and `ToolkitError` translated to the
  SDK's `ToolError` so deliberate messages reach the model.
- CI runs the suite on Python 3.11, 3.12 and 3.13.

### Deprecated

- `uv run toolkit.py` — it still starts the packaged server, for the sake of
  existing MCP client configurations, but `mct serve` is the documented
  invocation.

## [0.1.0] - 2026-08-30

First working version: a local, CPU-first image and video toolkit exposed over
MCP. Later commits in the same week shipped under this version too, and are
listed here.

### Added

- The original twelve tools, all local and CPU-only.
- `generate_image_free`, the one tool that leaves the machine, via
  Pollinations.ai.
- `upscale_image` (Upscayl), with its Intel iGPU performance limitation
  documented rather than hidden.
- `upscale_image_fast`: CPU-only FSRCNN super-resolution, sub-second.
- `strip_metadata`, `add_watermark` and `extract_audio` — local, no new heavy
  dependencies.
- An end-to-end pytest suite, and CI running it on push and pull request.

### Fixed

- `video_trim` no longer falls back silently, and no longer leaks its palette
  file; input guards added.
- `upscale_image` reads its Upscayl paths from environment variables instead of
  a hardcoded personal path.
- `remove_background` selects `u2net` (Apache-2.0) explicitly. `rembg`'s own
  no-argument default silently resolves to a CC BY-NC 4.0 model.
