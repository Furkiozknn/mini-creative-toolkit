"""Backwards-compatible launcher.

`uv run toolkit.py` was the documented way to start this server before 2.0,
and existing MCP client configurations still say exactly that. This keeps
working; it simply starts the packaged server.

The equivalent modern invocations are `mct serve` and
`python -m mini_creative_toolkit`.
"""

import sys
from pathlib import Path

# Support running straight from a checkout, before `uv sync` has installed the
# package - which is exactly the situation an old config would be in.
_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mini_creative_toolkit.server import main  # noqa: E402

if __name__ == "__main__":
    main()
