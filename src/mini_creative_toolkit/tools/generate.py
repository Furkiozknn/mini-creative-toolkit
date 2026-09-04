"""The one hosted tool. Everything about it is disclosed, nothing is implied."""

from __future__ import annotations

from .. import results
from ..config import Config, get_config
from ..engines import pollinations
from ..engines.images import EXTENSION_FOR
from ..log import get_logger
from ..paths import OutputManager
from ..validation import require_positive_int, require_text

logger = get_logger(__name__)

MAX_PROMPT_LENGTH = 1000


def generate_image_free(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
    client=None,
) -> dict | str:
    config = config or get_config()
    manager = OutputManager(config)
    prompt = require_text(prompt, "prompt", max_length=MAX_PROMPT_LENGTH)
    width = require_positive_int(width, "width", maximum=4096)
    height = require_positive_int(height, "height", maximum=4096)
    if seed is not None:
        seed = require_positive_int(seed, "seed", maximum=2**31 - 1)

    body, detected = pollinations.fetch_image(prompt, width, height, seed, config, client)
    ext = EXTENSION_FOR.get(detected, "jpg")

    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("generated", ext, destination) as staged:
        pollinations.save_image(body, staged.tmp)

    return results.build(
        "generate_image_free", staged.path, config=config,
        requested_width=width, requested_height=height, seed=seed,
        format=detected,
        disclosure=(
            f"The prompt text was sent to {pollinations.SERVICE_NAME}, a third-party "
            f"service. Nothing else in this toolkit makes network requests."
        ),
    )
