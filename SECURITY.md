# Security model

## The one sentence that matters

**This project is a local media-processing tool, not a sandbox.**

It runs as your user, with your user's file permissions. It reads any file
that user can read and writes into a directory that user can write. Running
it under an MCP client does not change that, and MCP does not make arbitrary
file access safe. If you need isolation, isolate the process — a container, a
dedicated user account, or a restricted mount — rather than relying on the
toolkit to provide it.

What the toolkit *does* provide is a set of narrow, checkable guarantees
about how it handles input. Those are documented below, along with what it
explicitly does not guarantee.

---

## Threat model

The realistic attacker is not someone with a shell on your machine — they
have already won. It is:

- **A malicious or manipulated tool call.** An MCP server's arguments are
  chosen by a model, and a model can be steered by text it read in a
  document, a web page, or a file it was asked to summarise. Every argument
  is treated as untrusted for that reason.
- **A hostile input file.** A 60000×60000 PNG that decompresses to gigabytes,
  a media file crafted to make ffmpeg misbehave, a file that is not what its
  extension claims.
- **A hostile response from the network.** The one hosted tool talks to a
  free public endpoint with no availability or integrity guarantee.

---

## What runs, and where

| Concern | Answer |
| --- | --- |
| Local file reads | Any file the running user can read (unless `MCT_ALLOWED_ROOTS` is set) |
| Local file writes | `MCT_OUTPUT_DIR` only, unless you pass an explicit `output_path` |
| Subprocesses | `ffmpeg`, `ffprobe`, and — only if you configured it — `upscayl-bin` |
| Network | One tool: `generate_image_free` → `image.pollinations.ai` |
| Model downloads | `rembg` fetches ONNX weights on the first use of a model |
| Credentials | None. The toolkit reads no API key, token, or password |

---

## Subprocess execution

`shell=True` appears nowhere in this repository, and a test enforces that by
parsing the AST of every module rather than grepping for the string. Commands
are built as argument lists; the binary itself comes from `shutil.which`, not
from caller input.

The residual risk is therefore not shell injection but **argument
injection** — a value like `-vf` or `-i` landing in `argv` where ffmpeg reads
it as an option instead of as data. Two things prevent it:

1. **Paths are always absolute.** `paths.resolve_input` returns a resolved
   absolute path, so every path argument begins with `/` and cannot be read
   as a flag.
2. **Non-path values are constrained to shapes that cannot start with `-`.**
   Timestamps must match a digits-and-colons grammar far narrower than
   ffmpeg's own parser. Model, codec and preset names must be a bare
   identifier — no dots, no slashes, no leading dash. Numbers are range-checked.

Rejected values are rejected, never sanitised. Quietly rewriting `-ss` into
something harmless would hide the attempt.

Every subprocess has a timeout (`MCT_SUBPROCESS_TIMEOUT`, default 900s), so a
pathological input cannot hang the server forever.

---

## Path handling

Paths from an MCP client are untrusted input. Resolution is:

1. Reject non-strings, empty strings, and anything containing a NUL byte.
2. `expanduser()`, then `resolve()` — which collapses `..` **and follows
   symlinks**. This ordering is the point: the allowed-root check runs on the
   real location, so neither `a/../../etc/passwd` nor a symlink planted inside
   an allowed root can escape it.
3. If `MCT_ALLOWED_ROOTS` is set, require the resolved path to be inside one
   of those roots.
4. A single `stat()` decides existence, type and size. Directories, FIFOs,
   devices and sockets are refused — ffmpeg would block forever on a FIFO.
5. Enforce `MCT_MAX_INPUT_MB`.

**`MCT_ALLOWED_ROOTS` is unset by default.** That is the historical behaviour
and it is stated here rather than disguised: with no roots configured, the
toolkit reads whatever the user can read. If you are exposing this to a model
you do not fully trust, set it:

```bash
export MCT_ALLOWED_ROOTS="$HOME/media:$HOME/projects/assets"
```

Multiple roots are separated by the platform path separator (`:` on Unix,
`;` on Windows).

---

## Output handling

- Outputs go to `MCT_OUTPUT_DIR`, default `output/` in the repository.
- **Nothing ever overwrites the input.** Every operation writes a new file.
- An explicit `output_path` will not replace an existing file unless you also
  pass `overwrite=true`.
- Writes are staged: the engine writes to a sibling temporary file, and it is
  renamed into place only after the operation succeeds and passes the output
  size check. A crashed ffmpeg leaves no truncated `.mp4` behind, and no
  intermediate (a GIF palette, for instance) survives a failure.
- Generated names carry a timestamp *and* random bytes, so concurrent batch
  workers cannot collide.
- The server removes leftover `*.part-*` files from a previously crashed run
  at startup.

---

## Resource limits

Every limit is configurable and every error names the limit it hit, so you can
tell "this file is too big" from "this tool is broken".

| Variable | Default | Guards against |
| --- | --- | --- |
| `MCT_MAX_INPUT_MB` | 512 | Reading an enormous file into memory |
| `MCT_MAX_OUTPUT_MB` | 1024 | Producing one |
| `MCT_MAX_IMAGE_PIXELS` | 80,000,000 | Decompression bombs. Checked from the header **before** pixels are decoded |
| `MCT_MAX_VIDEO_DURATION` | 3600s | Multi-hour transcodes |
| `MCT_MAX_VIDEO_WIDTH` / `_HEIGHT` | 7680 | Absurd resolutions |
| `MCT_MAX_BATCH_ITEMS` | 200 | Unbounded batches |
| `MCT_BATCH_CONCURRENCY` | 4 | Saturating the machine |
| `MCT_HEAVY_BATCH_CONCURRENCY` | 2 | The same, for CPU-heavy work |
| `MCT_MAX_DOWNLOAD_MB` | 64 | An unbounded hosted response |
| `MCT_HTTP_TIMEOUT` | 60s | A hosted call that never returns |
| `MCT_SUBPROCESS_TIMEOUT` | 900s | An ffmpeg run that never returns |

GIF generation additionally refuses a request whose `fps × duration` would
produce an unreasonable frame count, because the individual caps are not
sufficient on their own.

---

## The one network call

`generate_image_free` is the only tool that leaves the machine. It is
isolated in `engines/pollinations.py` so that "what does this server send
anywhere?" has a one-file answer, and a test asserts that no other module
imports an HTTP client or contains an outbound URL.

**Your prompt text is sent to a third party.** Do not put confidential
information in it. The service requires no API key today; that is its current
policy, not a guarantee.

The response is never trusted:

- Status codes ≥400 are refused, with 401/403 called out specifically — that
  would mean the endpoint has started requiring authentication.
- The `Content-Type` must be an image type. An HTML error page served with
  HTTP 200 is refused rather than written out as a `.jpg`.
- The body is read with a byte budget while streaming, so a response with no
  length header cannot stream forever.
- **The bytes are decoded before they are saved.** A correct content type is
  a claim; decoding is evidence. A truncated transfer is refused.

If the service disappears, changes, or starts requiring a key, nothing else
in the toolkit is affected.

---

## Model and binary downloads

- **FSRCNN weights ship inside the package.** Nothing is downloaded.
- **rembg downloads ONNX weights on first use** of a model it has not cached.
  This is disclosed in the tool description and in `list_capabilities`, where
  `remove_background` is marked `network: first-run-only`.
- **Upscayl is never downloaded.** Both its binary and its models must already
  exist on your machine and be pointed at by `UPSCAYL_BIN_PATH` and
  `UPSCAYL_MODELS_PATH`. The toolkit will not fetch or install them.

The toolkit never downloads and executes a binary.

---

## Logging

Logs go to **stderr**, never stdout — an MCP stdio server speaks JSON-RPC on
stdout, and a stray log line there corrupts the protocol stream.

Never logged at any level: environment variable values, HTTP request or
response bodies, file contents, or the prompt passed to the hosted generator.
Hosted calls log the service name and the operation only. There are no
credentials in this project to leak, and a test checks that no logging call
interpolates anything credential-shaped.

Verbose mode (`MCT_LOG_LEVEL=verbose`) adds the `detail` field of errors —
an ffmpeg stderr tail, for instance. That is deliberately *not* on by default:
forty kilobytes of ffmpeg banner pasted into a model's context is worse than
useless.

---

## MCP client considerations

- Tool descriptions state where each tool runs, what it needs, and what it
  costs. They are generated from a single capability table, so a description
  cannot drift away from the declared requirements.
- The server makes **no global claim** about being CPU-only or offline,
  because two of its tools would make such a claim false. Requirements are
  declared per tool.
- Call `list_capabilities` to see what this specific installation can actually
  run, including which tools are blocked and why.
- A model that is told to "process the file at `/etc/shadow`" will send that
  path. `MCT_ALLOWED_ROOTS` is the mechanism that stops it; nothing else will.

---

## What this project does NOT guarantee

- **It is not a sandbox.** It does not contain, isolate, or restrict what the
  underlying tools can do beyond what is described above.
- **It does not make ffmpeg or Pillow safe.** Both are large C codebases that
  parse hostile input. A vulnerability in either is reachable through this
  toolkit. Keep them updated.
- **It does not verify model licences for you.** Where a model's licence was
  not confirmed against a primary source, `list_background_models` says
  `not verified` rather than guessing. Check before commercial use.
- **It does not guarantee the hosted service's behaviour, privacy policy, or
  continued availability.** It only guarantees that it is the sole outbound
  call and that its response is validated before use.
- **It does not protect against a compromised MCP client.** A client that can
  call these tools can read and write files as your user.

---

## Reporting a problem

Open an issue at
<https://github.com/Furkiozknn/mini-creative-toolkit/issues>. For anything you
believe is genuinely exploitable, please describe the impact rather than
posting a working exploit in a public issue.
