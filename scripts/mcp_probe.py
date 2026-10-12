#!/usr/bin/env python3
"""Talk to the server the way an MCP client does, and print what it really says.

    python scripts/mcp_probe.py photo.jpg            # handshake, tool list, three real calls
    python scripts/mcp_probe.py photo.jpg --json     # the raw JSON-RPC replies instead

Starts `python -m mini_creative_toolkit` over stdio (the same process
`mct serve` and `toolkit.py` start), sends `initialize`, `tools/list` and real
`tools/call` requests, and checks every tool description for characters a
reader cannot see. It writes into a temporary output directory and never
touches the input file. Nothing here is mocked and nothing needs the network.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Client:
    def __init__(self, env: dict) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "mini_creative_toolkit"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1, env=env,
        )
        self.lines: queue.Queue = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()
        self.next_id = 0

    def _pump(self) -> None:
        for line in self.proc.stdout:  # type: ignore[union-attr]
            self.lines.put(line)

    def request(self, method: str, params: dict | None = None, timeout: float = 120.0) -> dict:
        self.next_id += 1
        message = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if params is not None:
            message["params"] = params
        self.proc.stdin.write(json.dumps(message) + "\n")  # type: ignore[union-attr]
        self.proc.stdin.flush()  # type: ignore[union-attr]
        while True:
            try:
                line = self.lines.get(timeout=timeout)
            except queue.Empty:
                raise SystemExit(f"mcp_probe: no answer to {method} within {timeout:.0f} s")
            if line.strip():
                return json.loads(line)

    def notify(self, method: str) -> None:
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")  # type: ignore[union-attr]
        self.proc.stdin.flush()  # type: ignore[union-attr]

    def call(self, name: str, arguments: dict) -> dict:
        reply = self.request("tools/call", {"name": name, "arguments": arguments})
        result = reply["result"]
        if result.get("isError"):
            raise SystemExit(f"mcp_probe: {name} failed: {result['content'][0]['text']}")
        return json.loads(result["content"][0]["text"])

    def close(self) -> None:
        self.proc.stdin.close()  # type: ignore[union-attr]
        self.proc.terminate()
        self.proc.wait(timeout=30)


def invisible(text: str) -> list[str]:
    """Format/control characters (zero-width, bidi, tags) other than ordinary whitespace."""
    return sorted({f"U+{ord(c):04X}" for c in text
                   if unicodedata.category(c) in ("Cf", "Cc") and c not in "\n\r\t"})


def main(argv: list[str]) -> int:
    raw = "--json" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    image = str(Path(args[0]).resolve())
    with tempfile.TemporaryDirectory(prefix="mct-probe-") as out:
        env = dict(os.environ, MCT_OUTPUT_DIR=out, PYTHONUNBUFFERED="1")
        if (ROOT / "src" / "mini_creative_toolkit").is_dir():  # running from a checkout
            env["PYTHONPATH"] = str(ROOT / "src")
        client = Client(env)
        try:
            init = client.request("initialize", {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "mcp_probe", "version": "1"}})
            client.notify("notifications/initialized")
            tools = client.request("tools/list")["result"]["tools"]
            if raw:
                print(json.dumps(init, indent=2)[:1500])
                print(json.dumps(tools[:2], indent=2))
            info = init["result"]["serverInfo"]
            print(f"initialize  -> {info['name']} {info.get('version', '')} "
                  f"(protocol {init['result']['protocolVersion']})")
            hosted = [t["name"] for t in tools if "network: required" in t["description"]]
            print(f"tools/list  -> {len(tools)} tools, {len(tools) - len(hosted)} local, "
                  f"{len(hosted)} hosted ({', '.join(hosted)})")
            hidden = {t["name"]: invisible(t["description"]) for t in tools if invisible(t["description"])}
            longest = max(len(t["description"]) for t in tools)
            print(f"descriptions -> longest {longest} chars, "
                  f"{len(hidden)} with invisible characters")

            before = client.call("inspect_media", {"path": image})
            print(f"inspect_media   -> {before['format']} {before['width']}x{before['height']} "
                  f"has_exif={before['has_exif']}  execution={before['execution']} network={before['network']}")
            stripped = client.call("strip_metadata", {"image_path": image})
            print(f"strip_metadata  -> removed_exif={stripped['removed_exif']}  "
                  f"execution={stripped['execution']} network={stripped['network']}")
            after = client.call("inspect_media", {"path": stripped["output_path"]})
            print(f"inspect_media   -> has_exif={after['has_exif']}  "
                  f"execution={after['execution']} network={after['network']}")
            if raw:
                print(json.dumps(stripped, indent=2))
            return 1 if hidden else 0
        finally:
            client.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
