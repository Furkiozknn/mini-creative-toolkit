# Third-party components

This repository is MIT-licensed. **That licence covers this project's own
code and nothing else.** Model weights, external binaries and dependencies
carry their own terms, and some of them differ in ways that matter — one
bundled-adjacent model is non-commercial. This file exists so you do not have
to reverse-engineer that from a dependency tree.

## Bundled in this repository

### FSRCNN weights — `src/mini_creative_toolkit/models/FSRCNN_x{2,3,4}.pb`

Used by `upscale_image_fast`. About 40 KB each; they ship inside the Python
package so an installed wheel has them.

- **Origin:** [Saafke/FSRCNN_Tensorflow](https://github.com/Saafke/FSRCNN_Tensorflow),
  produced as part of OpenCV's `dnn_superres` GSoC project and referenced from
  OpenCV's own documentation.
- **Paper:** Dong et al., ["Accelerating the Super-Resolution Convolutional
  Neural Network"](https://arxiv.org/abs/1608.00367) (ECCV 2016).
- **Licence:** see the upstream repository. These weights are not covered by
  this project's MIT licence.

No other model weights or binaries are bundled here.

## Downloaded at runtime

### rembg model weights

`remove_background` uses [rembg](https://github.com/danielgatis/rembg), which
downloads a model's ONNX weights the first time that model is used and caches
them afterwards. Nothing is downloaded until you call the tool.

Licences differ per model. `list_background_models` reports what is known:

| Model | Licence |
| --- | --- |
| `u2net` (default) | Apache-2.0 (U²-Net upstream) |
| `u2netp` | Apache-2.0 (U²-Net upstream) |
| `u2net_human_seg` | Apache-2.0 (U²-Net upstream) |
| `isnet-general-use` | not verified |
| `birefnet-general` | not verified |
| `bria-rmbg` | **CC BY-NC 4.0 — non-commercial only** |
| anything else this rembg version offers | not verified |

"not verified" means exactly that: it was not checked against a primary
source, so no claim is made. Verify before relying on it commercially.

The `bria-rmbg` entry is why this toolkit always constructs an explicit rembg
session from an explicit model name. As of rembg 2.0.81, calling rembg's
`remove()` with no session resolves internally to `bria-rmbg` — a tool whose
docstring says nothing about licensing should not hand a caller a
non-commercial model by accident. A test pins that behaviour.

## Optional, never installed by this project

### Upscayl (Real-ESRGAN via Vulkan)

`upscale_image` reuses a local [Upscayl](https://github.com/upscayl/upscayl)
install: its `upscayl-bin` executable and its `resources/models` directory.

**Neither is bundled or downloaded here.** You install Upscayl yourself and
point `UPSCAYL_BIN_PATH` and `UPSCAYL_MODELS_PATH` at it. Upscayl's own
licence and the licences of the Real-ESRGAN models it ships are Upscayl's to
state — check them there.

### ffmpeg / ffprobe

Required for every video and audio operation, and for `inspect_media` on
non-image files. Not bundled, not installed by this project — you install it
through your system package manager. ffmpeg's licensing depends on how your
build was compiled (LGPL or GPL, depending on the enabled codecs).

## Python dependencies

| Package | Why it is here |
| --- | --- |
| `pillow` | Image decode/encode, resize, drawing. The workhorse |
| `rembg[cpu]` | Background removal. The `[cpu]` extra keeps the CUDA runtime out of the tree |
| `opencv-contrib-python` | `dnn_superres` for FSRCNN — it ships only in the `-contrib` build, not in plain `opencv-python` |
| `mcp[cli]` | The MCP server itself |
| `httpx` | The one hosted call. Chosen over `urllib` for streaming with a byte budget, which is what bounds an oversized response |

Each of these carries its own licence; consult the package metadata. Nothing
was added for convenience alone — see `PROJECT.md` for the dependency policy.
