"""``batch_process`` - one operation over many files, with failure isolated.

Three properties matter here and each is enforced rather than hoped for:

* **One bad file never loses the batch.** Every item is run inside its own
  try/except, and failures are collected alongside successes.
* **Concurrency is bounded and conservative.** CPU-heavy operations
  (background removal, super-resolution) get a lower cap than cheap ones,
  because saturating every core with ONNX sessions on a laptop is how you
  make a "batch of 20" take longer than doing them one at a time.
* **Output is collision-free.** The output manager's random suffix is what
  makes that true under real parallelism, not the timestamp.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from ..config import Config, get_config
from ..errors import InvalidInputError, ResourceLimitError, ToolkitError
from ..log import get_logger
from ..paths import resolve_input_list
from .background import remove_background
from .image import add_watermark, convert_format, resize_image, strip_metadata
from .optimize import optimize_media
from .upscale import upscale_image_fast

logger = get_logger(__name__)



#: operation name -> (callable, is_cpu_heavy, required argument names)
OPERATIONS: dict[str, tuple[Callable, bool, tuple[str, ...]]] = {
    "resize": (resize_image, False, ("width", "height")),
    "convert_format": (convert_format, False, ("target_format",)),
    "strip_metadata": (strip_metadata, False, ()),
    "watermark": (add_watermark, False, ("text",)),
    "remove_background": (remove_background, True, ()),
    "optimize": (optimize_media, False, ()),
    "upscale_fast": (upscale_image_fast, True, ()),
}


def batch_process(
    paths: list[str],
    operation: str,
    options: dict | None = None,
    concurrency: int | None = None,
    config: Config | None = None,
) -> dict:
    config = config or get_config()

    if operation not in OPERATIONS:
        raise InvalidInputError(
            f"Unknown batch operation {operation!r}. Available: {', '.join(sorted(OPERATIONS))}"
        )
    func, heavy, required = OPERATIONS[operation]

    options = dict(options or {})
    if not isinstance(options, dict):
        raise InvalidInputError("options must be an object of keyword arguments")
    for key in ("output_path", "config"):
        # An explicit destination is meaningless for a batch: every item would
        # write to the same file. Refuse rather than silently ignore it.
        if key in options:
            raise InvalidInputError(
                f"options must not contain {key!r} - each batch item gets its own "
                f"generated output path."
            )
    missing = [name for name in required if name not in options]
    if missing:
        raise InvalidInputError(
            f"Batch operation {operation!r} needs these options: {', '.join(missing)}"
        )

    sources = resolve_input_list(paths, config, "paths")

    cap = config.heavy_batch_concurrency if heavy else config.batch_concurrency
    if concurrency is not None:
        if not isinstance(concurrency, int) or isinstance(concurrency, bool) or concurrency < 1:
            raise InvalidInputError(f"concurrency must be a positive integer, got {concurrency!r}")
        if concurrency > cap:
            raise ResourceLimitError(
                f"concurrency {concurrency} exceeds the configured cap of {cap} for "
                f"{'CPU-heavy' if heavy else 'standard'} operations. Raise "
                f"{'MCT_HEAVY_BATCH_CONCURRENCY' if heavy else 'MCT_BATCH_CONCURRENCY'} "
                f"to allow it.",
                limit_name="MCT_HEAVY_BATCH_CONCURRENCY" if heavy else "MCT_BATCH_CONCURRENCY",
                limit_value=cap,
                actual=concurrency,
            )
        workers = concurrency
    else:
        workers = cap
    workers = max(1, min(workers, len(sources)))

    logger.info(
        "batch_process: %s over %d files with %d worker(s)", operation, len(sources), workers
    )

    def run_one(index_and_path: tuple[int, Path]) -> dict:
        index, source = index_and_path
        try:
            outcome = func(str(source), config=config, **options)
        except ToolkitError as exc:
            return {"index": index, "input": str(source), "ok": False, **exc.to_dict(config.verbose)}
        except Exception as exc:  # a genuinely unexpected failure still isolates
            logger.debug("batch item %d failed unexpectedly", index, exc_info=True)
            return {
                "index": index,
                "input": str(source),
                "ok": False,
                "error": "unexpected_error",
                "message": f"{type(exc).__name__}: {exc}",
            }
        if isinstance(outcome, str):  # legacy string mode
            outcome = {"output_path": outcome}
        return {"index": index, "input": str(source), "ok": True, **outcome}

    if workers == 1:
        outcomes = [run_one(item) for item in enumerate(sources)]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            outcomes = list(pool.map(run_one, enumerate(sources)))

    outcomes.sort(key=lambda item: item["index"])
    succeeded = [o for o in outcomes if o["ok"]]
    failed = [o for o in outcomes if not o["ok"]]

    return {
        "operation": "batch_process",
        "execution": "local",
        "network": "none",
        "batch_operation": operation,
        "total": len(outcomes),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "concurrency": workers,
        "results": succeeded,
        "errors": failed,
    }
