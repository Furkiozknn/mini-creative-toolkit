"""rembg, with the model choice always made here and never by rembg itself.

The reason this is a whole module rather than two lines: as of rembg 2.0.81,
calling ``remove(data)`` with no session resolves internally to ``bria-rmbg``,
which is CC BY-NC 4.0 - non-commercial only. A tool whose docstring says
nothing about licensing must not hand a caller a non-commercial model by
accident, and that behaviour is undocumented enough to change again in either
direction across a version bump. So an explicit session is *always* built
from an explicit model name, and a test pins that.
"""

from __future__ import annotations

from pathlib import Path

from ..errors import InvalidInputError, MissingDependencyError, ModelUnavailableError
from ..log import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "u2net"

#: Characteristics we can state confidently. `license` is the licence of the
#: *model weights*, which is not this repository's MIT licence and is not
#: rembg's own licence either. Where the upstream licence could not be
#: confirmed from a primary source, it says so rather than guessing.
MODELS: dict[str, dict] = {
    "u2net": {
        "summary": "General-purpose default. Good balance of speed and quality.",
        "weights_mb": 176,
        "speed": "fast on CPU (~1-3s for a typical photo)",
        "license": "Apache-2.0 (U^2-Net upstream)",
        "license_verified": True,
    },
    "u2netp": {
        "summary": "Smaller, faster u2net. Softer edges.",
        "weights_mb": 4,
        "speed": "very fast on CPU",
        "license": "Apache-2.0 (U^2-Net upstream)",
        "license_verified": True,
    },
    "u2net_human_seg": {
        "summary": "u2net fine-tuned for people. Better on portraits than on objects.",
        "weights_mb": 176,
        "speed": "fast on CPU",
        "license": "Apache-2.0 (U^2-Net upstream)",
        "license_verified": True,
    },
    "isnet-general-use": {
        "summary": "IS-Net general model. Often crisper than u2net on hard edges.",
        "weights_mb": 179,
        "speed": "moderate on CPU",
        "license": "not verified",
        "license_verified": False,
    },
    "birefnet-general": {
        "summary": "BiRefNet. Noticeably better hair and fine-edge quality.",
        "weights_mb": 928,
        "speed": "slow on CPU - a cold session load alone can exceed a minute",
        "license": "not verified",
        "license_verified": False,
    },
    "bria-rmbg": {
        "summary": "BRIA RMBG. High quality, but see the licence.",
        "weights_mb": 176,
        "speed": "moderate on CPU",
        "license": "CC BY-NC 4.0 - non-commercial use only",
        "license_verified": True,
    },
}


def list_models() -> list[dict]:
    """Documented models plus whatever else this rembg install offers.

    Anything not in the curated table is reported with
    ``license: "not verified"`` - the honest answer, since we have not
    checked it, rather than a guess that could be wrong in the expensive
    direction.
    """
    known = [{"model": name, **info} for name, info in MODELS.items()]
    documented = set(MODELS)
    try:
        from rembg.sessions import sessions_names
    except Exception:  # pragma: no cover - depends on the rembg version
        return known
    for name in sorted(set(sessions_names) - documented):
        known.append(
            {
                "model": name,
                "summary": "Available in this rembg install but not documented here.",
                "weights_mb": None,
                "speed": "unknown",
                "license": "not verified",
                "license_verified": False,
            }
        )
    return known


def known_model_names() -> set[str]:
    names = set(MODELS)
    try:
        from rembg.sessions import sessions_names

        names |= set(sessions_names)
    except Exception:  # pragma: no cover
        pass
    return names


def remove_background(data: bytes, model: str = DEFAULT_MODEL) -> bytes:
    """Cut out the subject. Always with an explicitly constructed session."""
    try:
        import rembg
    except ImportError:  # pragma: no cover - rembg is a hard dependency
        raise MissingDependencyError("rembg is not installed.") from None

    available = known_model_names()
    if available and model not in available:
        raise InvalidInputError(
            f"Unknown background-removal model {model!r}. Known models: "
            f"{', '.join(sorted(available))}. Call list_background_models for details."
        )

    logger.info("remove_background: building an explicit rembg session for %s", model)
    try:
        session = rembg.new_session(model)
    except Exception as exc:
        # A cold model download that fails (offline, or the weights host is
        # down) surfaces here. Say which model, and that a download was
        # involved, rather than leaking a urllib traceback.
        raise ModelUnavailableError(
            f"Could not load the rembg model {model!r}. The first use of a model "
            f"downloads its weights, so this fails offline; after that it is local.",
            detail=repr(exc),
        ) from None
    try:
        return rembg.remove(data, session=session)
    except Exception as exc:
        raise ModelUnavailableError(
            f"Background removal with {model!r} failed.", detail=repr(exc)
        ) from None
