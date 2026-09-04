"""Named dimension presets.

These are a convenience so a caller does not have to remember that a vertical
video is 1080x1920. They are **not** a platform certification: no platform's
current requirements are encoded here, no platform branding is used, and any
of these numbers can be wrong for a given service on a given day. Override
them with ``MCT_PRESETS_*`` or just pass explicit dimensions.
"""

from __future__ import annotations

import os

from ..errors import InvalidInputError

IMAGE_PRESETS: dict[str, tuple[int, int]] = {
    "square": (1080, 1080),
    "portrait": (1080, 1350),
    "landscape": (1200, 630),
    "story": (1080, 1920),
    "wide": (1920, 1080),
    "thumbnail": (480, 480),
}

VIDEO_PRESETS: dict[str, tuple[int, int]] = {
    "vertical": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}

DISCLAIMER = (
    "These are convenience dimensions, not a guarantee that any particular "
    "platform will accept the result. Platform requirements change; verify "
    "against the platform's own current documentation before relying on them."
)


def _overrides(prefix: str, base: dict[str, tuple[int, int]]) -> dict[str, tuple[int, int]]:
    """``MCT_PRESETS_IMAGE_SQUARE=1200x1200`` replaces one entry."""
    resolved = dict(base)
    for name in base:
        raw = os.environ.get(f"{prefix}_{name.upper()}")
        if not raw:
            continue
        try:
            width, height = (int(part) for part in raw.lower().split("x", 1))
        except ValueError:
            raise InvalidInputError(
                f"{prefix}_{name.upper()} must look like '1080x1350', got {raw!r}"
            ) from None
        if width <= 0 or height <= 0:
            raise InvalidInputError(f"{prefix}_{name.upper()} dimensions must be positive")
        resolved[name] = (width, height)
    return resolved


def image_presets() -> dict[str, tuple[int, int]]:
    return _overrides("MCT_PRESETS_IMAGE", IMAGE_PRESETS)


def video_presets() -> dict[str, tuple[int, int]]:
    return _overrides("MCT_PRESETS_VIDEO", VIDEO_PRESETS)


def resolve(kind: str, name: object) -> tuple[int, int]:
    table = image_presets() if kind == "image" else video_presets()
    if not isinstance(name, str) or name.strip().lower() not in table:
        raise InvalidInputError(
            f"Unknown {kind} preset {name!r}. Available: {', '.join(sorted(table))}"
        )
    return table[name.strip().lower()]


def list_presets() -> dict:
    return {
        "operation": "list_presets",
        "execution": "local",
        "network": "none",
        "image": {name: {"width": w, "height": h} for name, (w, h) in image_presets().items()},
        "video": {name: {"width": w, "height": h} for name, (w, h) in video_presets().items()},
        "disclaimer": DISCLAIMER,
        "override": (
            "Set MCT_PRESETS_IMAGE_<NAME> or MCT_PRESETS_VIDEO_<NAME> to '<width>x<height>' "
            "to change any of these."
        ),
    }
