"""The shape every tool returns.

Before 2.0 each tool returned a bare path string. That is the minimum a
caller needs and nothing more: an MCP client that asked for a resize could
not tell what dimensions it actually got, whether alpha was flattened, or
whether the operation ran locally.

Tools now return a dict. ``output_path`` always carries what the old return
value carried, so a caller that only reads that one key keeps working. For
callers that genuinely need the old shape, ``MCT_LEGACY_STRING_RESULTS=1``
restores it verbatim.
"""

from __future__ import annotations

from pathlib import Path

from .capabilities import CAPABILITIES, ExecutionMode
from .config import Config, get_config
from .log import get_logger

logger = get_logger(__name__)


def build(
    operation: str,
    output_path: Path | None = None,
    config: Config | None = None,
    **fields,
) -> dict | str:
    """Assemble a structured result, honouring the legacy-output setting."""
    config = config or get_config()
    if config.legacy_string_results and output_path is not None:
        return str(output_path)

    cap = CAPABILITIES.get(operation)
    result: dict = {"operation": operation}
    if output_path is not None:
        result["output_path"] = str(output_path)
        try:
            result["output_size_bytes"] = output_path.stat().st_size
        except OSError:  # pragma: no cover - the file was just written
            pass
    if cap is not None:
        result["execution"] = cap.execution.value
        result["network"] = cap.network.value
        if cap.execution is ExecutionMode.HOSTED:
            result["external_service"] = cap.external_service
    result.update(fields)
    return result


def percent_change(before: int, after: int) -> float:
    """Signed percentage change, negative meaning the file got smaller."""
    if before <= 0:
        return 0.0
    return round((after - before) / before * 100.0, 2)
