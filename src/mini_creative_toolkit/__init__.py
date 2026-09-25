"""mini-creative-toolkit: local media operations exposed over MCP and a CLI."""

import os as _os

# onnxruntime's official Linux/macOS wheels start a telemetry uploader (the 1DS
# SDK, to mobile.events.data.microsoft.com) as soon as onnxruntime is imported,
# and rembg imports it. That is network traffic from tools this project reports
# as `network: none`. ORT_DISABLE_TELEMETRY=1 is onnxruntime's documented
# runtime switch and must be set before onnxruntime initialises, so it is set
# here, on package import, before any module that could pull rembg in. An
# explicit value in the environment is left alone.
_os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")

__version__ = "2.1.0"
__all__ = ["__version__"]
