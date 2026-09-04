"""Untrusted-path resolution and output management.

Paths reaching this module came from an MCP client, which means from a model,
which means they are attacker-influenceable in exactly the way a web form is.
Two separate concerns live here:

**Resolution.** Turn a caller string into a real, existing, regular file, or
refuse. ``Path.resolve()`` collapses ``..`` and follows symlinks *before* the
allowed-root check, so neither ``a/../../etc/passwd`` nor a symlink planted
inside an allowed root can escape it.

**Output.** Produce a fresh, collision-free path inside the output directory,
write to a sibling temporary file, and rename into place only on success -
so a crashed ffmpeg leaves no half-written ``.mp4`` for the caller to find,
and two concurrent batch workers cannot collide.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import Iterator, Sequence

from .config import Config, get_config
from .errors import InvalidInputError, PathPermissionError, ResourceLimitError

#: Filesystem-safe characters for the caller-visible part of an output name.
_SAFE_STEM = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"


def _reject_nul(raw: str, field: str) -> None:
    if "\x00" in raw:
        raise InvalidInputError(f"{field} must not contain a NUL byte")


def normalize(raw: object, field: str = "path") -> Path:
    """String -> absolute, symlink-free ``Path``. Does not require existence."""
    if not isinstance(raw, str):
        raise InvalidInputError(f"{field} must be a string, got {type(raw).__name__}")
    if not raw.strip():
        raise InvalidInputError(f"{field} must not be empty")
    _reject_nul(raw, field)
    try:
        candidate = Path(raw).expanduser()
    except RuntimeError as exc:  # expanduser() with an unresolvable ~user
        raise InvalidInputError(f"{field} could not be expanded: {exc}") from None
    try:
        return candidate.resolve()
    except OSError as exc:
        raise InvalidInputError(f"{field} could not be resolved: {exc}") from None


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def check_roots(path: Path, config: Config, field: str = "path") -> None:
    """Enforce ``MCT_ALLOWED_ROOTS`` when it is set.

    When it is unset the check is a no-op, which is the historical behaviour
    and is documented as such in SECURITY.md. An empty default is not a
    sandbox and this project does not claim it is one.
    """
    if not config.allowed_roots:
        return
    if any(is_within(path, root) for root in config.allowed_roots):
        return
    raise PathPermissionError(
        f"{field} resolves to {path}, which is outside the allowed roots "
        f"configured in MCT_ALLOWED_ROOTS ({', '.join(str(r) for r in config.allowed_roots)})"
    )


def resolve_input(raw: object, config: Config | None = None, field: str = "path") -> Path:
    """Resolve and fully validate a file the caller wants us to read."""
    config = config or get_config()
    path = normalize(raw, field)
    check_roots(path, config, field)

    # One stat() answers existence, type and size at once - and, crucially, it
    # is the only place an OSError can come from. Path.exists() re-raises
    # ENAMETOOLONG on Python 3.11, so an over-long path would otherwise leak a
    # raw OSError past every domain error in this module.
    try:
        stat_result = path.stat()
    except FileNotFoundError:
        raise InvalidInputError(f"No such file: {path}") from None
    except PermissionError:
        raise PathPermissionError(f"{field} is not accessible: {path}") from None
    except OSError as exc:
        raise InvalidInputError(f"{field} could not be read: {exc.strerror or exc}") from None

    if stat.S_ISDIR(stat_result.st_mode):
        raise InvalidInputError(f"{field} is a directory, not a file: {path}")
    if not stat.S_ISREG(stat_result.st_mode):
        # Named pipes, devices, sockets. ffmpeg would happily block forever on
        # a FIFO; Pillow would read garbage from /dev/urandom.
        raise InvalidInputError(f"{field} is not a regular file: {path}")
    if not os.access(path, os.R_OK):
        raise PathPermissionError(f"{field} is not readable: {path}")

    size = stat_result.st_size
    if size == 0:
        raise InvalidInputError(f"{field} is an empty file: {path}")
    if size > config.max_input_bytes:
        raise ResourceLimitError(
            f"{path.name} is {size / 1024 / 1024:.1f} MB, above the "
            f"{config.max_input_mb:g} MB input limit (raise MCT_MAX_INPUT_MB to allow it)",
            limit_name="MCT_MAX_INPUT_MB",
            limit_value=config.max_input_mb,
            actual=round(size / 1024 / 1024, 2),
        )
    return path


def resolve_input_list(
    raws: Sequence[object], config: Config | None = None, field: str = "paths"
) -> list[Path]:
    config = config or get_config()
    if not isinstance(raws, (list, tuple)):
        raise InvalidInputError(f"{field} must be a list of paths, got {type(raws).__name__}")
    if not raws:
        raise InvalidInputError(f"{field} must not be empty")
    if len(raws) > config.max_batch_items:
        raise ResourceLimitError(
            f"{field} has {len(raws)} entries, above the {config.max_batch_items} item limit "
            f"(raise MCT_MAX_BATCH_ITEMS to allow it)",
            limit_name="MCT_MAX_BATCH_ITEMS",
            limit_value=config.max_batch_items,
            actual=len(raws),
        )
    return [resolve_input(raw, config, f"{field}[{i}]") for i, raw in enumerate(raws)]


def safe_stem(raw: str, fallback: str = "output", max_length: int = 60) -> str:
    """Reduce an arbitrary name to something safe to put in a filename."""
    cleaned = "".join(c if c in _SAFE_STEM else "-" for c in raw).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return (cleaned[:max_length] or fallback)


def normalize_extension(ext: str, fallback: str = "png") -> str:
    cleaned = safe_stem(ext.lower().lstrip("."), fallback=fallback, max_length=12)
    return cleaned or fallback


class OutputManager:
    """Owns everything written under ``config.output_dir``."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or get_config()

    @property
    def directory(self) -> Path:
        return self.config.output_dir

    def ensure_directory(self) -> Path:
        directory = self.directory
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PathPermissionError(f"Could not create output directory {directory}: {exc}") from None
        return directory

    def allocate(self, prefix: str, ext: str) -> Path:
        """A path that does not exist yet, inside the output directory.

        The random suffix is what makes this safe under the batch executor:
        a bare timestamp collides when two workers finish in the same
        microsecond, and the retry loop below would then spin.
        """
        directory = self.ensure_directory()
        prefix = safe_stem(prefix, fallback="output")
        ext = normalize_extension(ext)
        for _ in range(64):
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            candidate = directory / f"{prefix}-{stamp}-{secrets.token_hex(3)}.{ext}"
            if not candidate.exists():
                return candidate
        raise PathPermissionError(f"Could not allocate a free output name in {directory}")

    def resolve_explicit(self, raw: object, overwrite: bool, field: str = "output_path") -> Path:
        """Validate a caller-chosen destination.

        ``overwrite`` defaults to false everywhere it is exposed; this is the
        single place that decides whether an existing file may be replaced.
        """
        path = normalize(raw, field)
        check_roots(path, self.config, field)
        if path.is_dir():
            raise InvalidInputError(f"{field} is a directory: {path}")
        if path.exists() and not overwrite:
            raise InvalidInputError(
                f"{path} already exists. Pass overwrite=true to replace it, or choose another path."
            )
        parent = path.parent
        if not parent.is_dir():
            raise InvalidInputError(f"Directory does not exist: {parent}")
        if not os.access(parent, os.W_OK):
            raise PathPermissionError(f"Directory is not writable: {parent}")
        return path

    def stage(self, prefix: str, ext: str, destination: Path | None = None) -> "_Staged":
        """Open a staged write: a temp file that is renamed into place on success.

        Usage::

            with manager.stage("resized", "png") as out:
                img.save(out.tmp)
            return out.path

        On any exception the temporary file is removed, so a failed ffmpeg
        run cannot leave a truncated artefact behind.
        """
        return _Staged(self, prefix, ext, destination)

    def enforce_output_size(self, path: Path) -> None:
        size = path.stat().st_size
        if size > self.config.max_output_bytes:
            path.unlink(missing_ok=True)
            raise ResourceLimitError(
                f"Output would be {size / 1024 / 1024:.1f} MB, above the "
                f"{self.config.max_output_mb:g} MB limit (raise MCT_MAX_OUTPUT_MB to allow it)",
                limit_name="MCT_MAX_OUTPUT_MB",
                limit_value=self.config.max_output_mb,
                actual=round(size / 1024 / 1024, 2),
            )

    def cleanup_partials(self) -> int:
        """Remove leftover ``.part-*`` files from crashed earlier runs."""
        directory = self.directory
        if not directory.is_dir():
            return 0
        removed = 0
        for entry in directory.glob("*.part-*"):
            with contextlib.suppress(OSError):
                entry.unlink()
                removed += 1
        return removed


class _Staged:
    """Context manager yielding ``.tmp``; exposes ``.path`` after the block."""

    def __init__(
        self, manager: OutputManager, prefix: str, ext: str, destination: Path | None
    ) -> None:
        self._manager = manager
        self._prefix = prefix
        self._ext = normalize_extension(ext)
        self._destination = destination
        self.path: Path | None = None
        self.tmp: Path | None = None

    def __enter__(self) -> "_Staged":
        if self._destination is not None:
            final = self._destination
        else:
            final = self._manager.allocate(self._prefix, self._ext)
        self._final = final
        final.parent.mkdir(parents=True, exist_ok=True)
        ext = normalize_extension(final.suffix or self._ext)
        self.tmp = final.with_name(f"{final.stem}.part-{secrets.token_hex(4)}.{ext}")
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        assert self.tmp is not None
        if exc_type is not None:
            self.tmp.unlink(missing_ok=True)
            return False
        if not self.tmp.exists():
            raise PathPermissionError(
                f"Operation reported success but wrote no output for {self._final.name}"
            )
        self._manager.enforce_output_size(self.tmp)
        try:
            os.replace(self.tmp, self._final)
        except OSError:
            # Cross-device rename (output dir on another filesystem than the
            # temp sibling cannot happen here, but a network mount can still
            # refuse). Fall back to copy+unlink rather than losing the result.
            shutil.move(str(self.tmp), str(self._final))
        self.path = self._final
        return False


@contextlib.contextmanager
def scratch_file(manager: OutputManager, prefix: str, ext: str) -> Iterator[Path]:
    """A temporary file that is always removed, success or failure.

    Used for intermediates that must never survive - the GIF palette being
    the case that actually bit this project once.
    """
    manager.ensure_directory()
    path = manager.allocate(f"tmp-{prefix}", ext)
    try:
        yield path
    finally:
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)
