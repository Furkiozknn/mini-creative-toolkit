"""Logging: three levels, and a hard rule about what never gets logged.

Never logged, at any level: environment variable *values*, HTTP request or
response bodies, file contents. Hosted calls log the service name and the
operation - not the prompt, which is user content that may be sensitive and
which is already leaving the machine once without needing to also land in a
log file.
"""

from __future__ import annotations

import logging
import os
import sys

LEVELS = {"quiet": logging.ERROR, "normal": logging.INFO, "verbose": logging.DEBUG}

_ROOT = "mini_creative_toolkit"
_configured = False


def get_logger(name: str = _ROOT) -> logging.Logger:
    return logging.getLogger(name)


def configure(level: str | None = None, stream=None) -> logging.Logger:
    """Attach a handler to the package logger. Safe to call repeatedly.

    Logs go to stderr on purpose: an MCP stdio server speaks JSON-RPC on
    stdout, and a stray log line there corrupts the protocol stream.
    """
    global _configured
    level = (level or os.environ.get("MCT_LOG_LEVEL") or "normal").lower()
    logger = logging.getLogger(_ROOT)
    logger.setLevel(LEVELS.get(level, logging.INFO))
    if not _configured or stream is not None:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        handler = logging.StreamHandler(stream or sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
        _configured = True
    return logger
