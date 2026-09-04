"""``inspect_media`` and ``list_capabilities`` - the two read-only tools."""

from __future__ import annotations

from ..capabilities import CAPABILITIES, probe_environment, readiness
from ..config import Config, get_config
from ..media_info import describe
from ..paths import resolve_input


def inspect_media(path: str, config: Config | None = None) -> dict:
    """Describe a media file without modifying or writing anything."""
    config = config or get_config()
    source = resolve_input(path, config, "path")
    info = describe(source, config)
    return {"operation": "inspect_media", "execution": "local", "network": "none", **info}


def list_capabilities(config: Config | None = None) -> dict:
    """What every tool requires, and whether this machine can currently run it."""
    config = config or get_config()
    env = probe_environment(config)
    ready = readiness(config)
    tools = []
    for name, cap in CAPABILITIES.items():
        entry = cap.to_dict()
        entry.update(ready[name])
        tools.append(entry)
    return {
        "operation": "list_capabilities",
        "execution": "local",
        "network": "none",
        "tools": tools,
        "environment": env,
        "limits": config.limits_dict(),
        "notes": [
            "Exactly one tool (generate_image_free) makes a network request. Every "
            "other tool runs entirely on this machine.",
            "remove_background is listed as network 'first-run-only' because rembg "
            "downloads model weights the first time a given model is used.",
            "This server is not a sandbox. It reads and writes files with the "
            "permissions of the user running it - see SECURITY.md.",
        ],
    }
