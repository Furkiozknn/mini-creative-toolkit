"""Background removal, with the model choice always explicit."""

from __future__ import annotations

from .. import results
from ..config import Config, get_config
from ..engines import background as engine
from ..engines import images
from ..log import get_logger
from ..paths import OutputManager, resolve_input
from ..validation import require_name

logger = get_logger(__name__)


def remove_background(
    image_path: str,
    model: str = engine.DEFAULT_MODEL,
    output_path: str | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict | str:
    config = config or get_config()
    manager = OutputManager(config)
    source = resolve_input(image_path, config, "image_path")
    model = require_name(model, "model")

    width, height, _ = images.header_size(source)
    images.check_pixel_budget(width, height, source, config)

    payload = source.read_bytes()
    output_bytes = engine.remove_background(payload, model)

    destination = manager.resolve_explicit(output_path, overwrite) if output_path else None
    with manager.stage("nobg", "png", destination) as staged:
        staged.tmp.write_bytes(output_bytes)

    info = engine.MODELS.get(model, {})
    return results.build(
        "remove_background", staged.path, config=config,
        input=str(source), model=model,
        model_license=info.get("license", "not verified"),
        model_license_verified=bool(info.get("license_verified", False)),
        width=width, height=height,
    )


def list_background_models(config: Config | None = None) -> dict:
    """Every model this rembg install offers, with what we can honestly say."""
    models = engine.list_models()
    return {
        "operation": "list_background_models",
        "execution": "local",
        "network": "none",
        "default": engine.DEFAULT_MODEL,
        "models": models,
        "notes": [
            "Weights are downloaded on the first use of a model and cached afterwards; "
            "that first run needs network access.",
            "Model licences are not this repository's MIT licence and differ between "
            "models. Entries marked 'not verified' were not checked against a primary "
            "source - verify before commercial use rather than assuming.",
            "This toolkit always builds an explicit rembg session from the model name. "
            "It never falls back to rembg's own internal default, which as of rembg "
            "2.0.81 is the non-commercial 'bria-rmbg'.",
        ],
    }
