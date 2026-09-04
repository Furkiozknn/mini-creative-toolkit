"""Domain errors.

Every error carries two levels of text: `message`, which is what an MCP
client (and therefore a model) sees, and `detail`, which holds the raw
diagnostic - an ffmpeg log, a traceback string, a full stderr dump. The
detail is only surfaced when verbose logging is on, because a 40KB ffmpeg
log pasted into a model's context is worse than useless.
"""

from __future__ import annotations


class ToolkitError(Exception):
    """Base class for every error this toolkit raises deliberately."""

    #: Short machine-readable tag, surfaced in structured results.
    code = "toolkit_error"

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def describe(self, verbose: bool = False) -> str:
        if verbose and self.detail:
            return f"{self.message}\n--- detail ---\n{self.detail}"
        return self.message

    def to_dict(self, verbose: bool = False) -> dict:
        out = {"error": self.code, "message": self.message}
        if verbose and self.detail:
            out["detail"] = self.detail
        return out


class InvalidInputError(ToolkitError):
    """A caller-supplied value is malformed, out of range, or nonsensical."""

    code = "invalid_input"


class UnsupportedFormatError(InvalidInputError):
    """The requested format exists but this installation cannot handle it."""

    code = "unsupported_format"


class MissingDependencyError(ToolkitError):
    """A required external program or Python package is not installed."""

    code = "missing_dependency"


class ExternalToolError(ToolkitError):
    """An external program ran but failed. `detail` holds its stderr tail."""

    code = "external_tool_error"


class ResourceLimitError(ToolkitError):
    """A configured safety limit was exceeded.

    The message always names the limit and its configured value, so the
    caller can decide whether to raise it rather than guess what happened.
    """

    code = "resource_limit"

    def __init__(self, message: str, limit_name: str, limit_value: object, actual: object = None) -> None:
        super().__init__(message)
        self.limit_name = limit_name
        self.limit_value = limit_value
        self.actual = actual

    def to_dict(self, verbose: bool = False) -> dict:
        out = super().to_dict(verbose)
        out.update({"limit": self.limit_name, "limit_value": self.limit_value})
        if self.actual is not None:
            out["actual"] = self.actual
        return out


class ModelUnavailableError(ToolkitError):
    """A model (rembg session, FSRCNN weights, Upscayl models) is not usable."""

    code = "model_unavailable"


class NetworkError(ToolkitError):
    """A hosted call failed: timeout, connection error, bad status, bad body."""

    code = "network_error"


class PathPermissionError(ToolkitError):
    """A path is outside the configured allowed roots, or is unreadable.

    Deliberately *not* named ``PermissionError`` - shadowing the builtin
    inside a package that also catches OSError subclasses is a trap.
    """

    code = "path_permission"
