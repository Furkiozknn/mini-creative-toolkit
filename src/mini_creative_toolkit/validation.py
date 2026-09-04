"""Validators for every value that reaches a subprocess argument list.

The threat model is narrow and specific: this is an MCP server, so a model
- possibly steered by text it read somewhere - chooses these values. None of
them is ever concatenated into a shell string (see ``engines/ffmpeg.py``:
``shell=True`` appears nowhere in this repository), so the risk is not shell
injection. It is *argument* injection: a value like ``-vf`` or ``-f`` landing
in argv where ffmpeg would read it as a new option rather than as data.

The defence is the same everywhere: constrain each value to a shape that
cannot be read as an option, and reject rather than sanitise. Silently
rewriting a hostile value into a benign one hides the attempt.
"""

from __future__ import annotations

import re

from .errors import InvalidInputError

#: ``HH:MM:SS``, ``MM:SS``, ``SS``, each optionally with a fractional part.
#: Anchored, digits and separators only - nothing here can begin with ``-``.
_TIMESTAMP_RE = re.compile(r"^(?:(?:\d{1,3}:)?[0-5]?\d:)?[0-5]?\d(?:\.\d{1,6})?$")

#: Model / preset / codec names: what ffmpeg, rembg and Upscayl actually use.
#: No dots (no path traversal), no slashes, no leading dash.
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def require_timestamp(value: object, field: str = "timestamp") -> str:
    """Accept ``HH:MM:SS[.mmm]``/``MM:SS``/``SS``; reject anything else.

    ffmpeg's own ``-ss`` parser is far more permissive than this - it happily
    takes ``-ss -0:30`` and other shapes. Narrowing to this grammar is what
    guarantees the value can never be mistaken for an option.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < 0:
            raise InvalidInputError(f"{field} must not be negative, got {value}")
        return f"{float(value):.6f}"
    if not isinstance(value, str):
        raise InvalidInputError(f"{field} must be a string like '00:00:05', got {type(value).__name__}")
    candidate = value.strip()
    if not _TIMESTAMP_RE.match(candidate):
        raise InvalidInputError(
            f"{field} must look like HH:MM:SS, MM:SS or SS (optionally with a "
            f"decimal fraction), got {value!r}"
        )
    return candidate


def require_positive_number(value: object, field: str, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidInputError(f"{field} must be a number, got {type(value).__name__}")
    if value <= 0:
        raise InvalidInputError(f"{field} must be > 0, got {value}")
    if maximum is not None and value > maximum:
        raise InvalidInputError(f"{field} must be <= {maximum}, got {value}")
    return float(value)


def require_positive_int(value: object, field: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        # Accept an integral float (JSON has no int/float distinction, and MCP
        # arguments arrive as JSON), but not 3.5.
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        else:
            raise InvalidInputError(f"{field} must be an integer, got {value!r}")
    if value <= 0:
        raise InvalidInputError(f"{field} must be > 0, got {value}")
    if maximum is not None and value > maximum:
        raise InvalidInputError(f"{field} must be <= {maximum}, got {value}")
    return int(value)


def require_ratio(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidInputError(f"{field} must be a number between 0 and 1, got {value!r}")
    if not 0.0 <= value <= 1.0:
        raise InvalidInputError(f"{field} must be between 0 and 1, got {value}")
    return float(value)


def require_name(value: object, field: str, allowed: set[str] | None = None) -> str:
    """A short identifier: model name, codec, preset, goal."""
    if not isinstance(value, str):
        raise InvalidInputError(f"{field} must be a string, got {type(value).__name__}")
    candidate = value.strip()
    if not _NAME_RE.match(candidate):
        raise InvalidInputError(
            f"{field} must be letters, digits, '-' or '_' (1-64 chars, not "
            f"starting with '-'), got {value!r}"
        )
    if allowed is not None and candidate not in allowed:
        raise InvalidInputError(f"{field} must be one of {sorted(allowed)}, got {candidate!r}")
    return candidate


def require_choice(value: object, field: str, allowed: set[str]) -> str:
    if not isinstance(value, str):
        raise InvalidInputError(f"{field} must be a string, got {type(value).__name__}")
    candidate = value.strip().lower()
    if candidate not in allowed:
        raise InvalidInputError(f"{field} must be one of {sorted(allowed)}, got {value!r}")
    return candidate


def require_text(value: object, field: str, max_length: int = 500) -> str:
    """Free text that is *drawn*, never executed - watermark captions, labels.

    Control characters are rejected rather than stripped: a caption
    containing an ANSI escape or a NUL is a sign something is wrong upstream,
    and quietly drawing a mangled version of it would hide that.
    """
    if not isinstance(value, str):
        raise InvalidInputError(f"{field} must be a string, got {type(value).__name__}")
    if not value.strip():
        # Whitespace-only counts as empty. A blank prompt reaching the hosted
        # generator would be a pointless outbound request; a blank watermark
        # would draw nothing and report success.
        raise InvalidInputError(f"{field} must not be empty")
    if len(value) > max_length:
        raise InvalidInputError(f"{field} must be at most {max_length} characters, got {len(value)}")
    bad = {c for c in value if ord(c) < 32 or ord(c) == 127}
    if bad:
        raise InvalidInputError(
            f"{field} must not contain control characters (found "
            f"{', '.join(sorted(hex(ord(c)) for c in bad))})"
        )
    return value
