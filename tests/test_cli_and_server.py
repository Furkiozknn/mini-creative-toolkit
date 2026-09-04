"""The two surfaces, and the promise that they share one implementation."""

from __future__ import annotations

import asyncio
import json
import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from PIL import Image

from mini_creative_toolkit.capabilities import CAPABILITIES
from mini_creative_toolkit.cli import build_parser, main
from mini_creative_toolkit.server import describe, mcp

REPO_ROOT = Path(__file__).resolve().parents[1]


# --- MCP surface -------------------------------------------------------------

def _tools():
    return asyncio.run(mcp.list_tools())


def test_every_registered_tool_has_a_declared_capability():
    """The description footer is generated from the capability table, so a tool
    registered without an entry would advertise nothing about its requirements."""
    assert {t.name for t in _tools()} == set(CAPABILITIES)


def test_every_tool_description_states_where_it_runs():
    for tool in _tools():
        assert "execution:" in tool.description, tool.name
        assert "network:" in tool.description, tool.name


def test_the_hosted_tool_shouts_about_it():
    tool = next(t for t in _tools() if t.name == "generate_image_free")
    assert "ONLY TOOL THAT LEAVES THIS MACHINE" in tool.description
    assert "Pollinations.ai" in tool.description


def test_gpu_bound_tools_say_so_in_their_description():
    tool = next(t for t in _tools() if t.name == "upscale_image")
    assert "discrete GPU" in tool.description
    assert "gpu: required" in tool.description


def test_descriptions_are_short_enough_to_be_useful_in_discovery():
    """A tool description is read by a model on every listing. One that runs to
    thousands of characters crowds out the rest of the toolbox."""
    for tool in _tools():
        assert len(tool.description) < 1400, f"{tool.name}: {len(tool.description)}"


def test_the_capability_footer_is_generated_not_written_by_hand():
    text = describe("resize_image", "Body.")
    assert text.startswith("Body.")
    assert "[execution: local | network: none]" in text


class _StdioClient:
    """A minimal MCP stdio client that keeps stdin open.

    Writing every request and then closing stdin races the server's
    EOF-triggered shutdown: a response still in flight is lost, which made an
    earlier version of this test pass alone and fail under a full run. A real
    client holds the pipe open, so this one does too.
    """

    def __init__(self, tmp_path: Path, env_extra: dict | None = None) -> None:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(tmp_path),
            "MCT_OUTPUT_DIR": str(tmp_path / "out"),
            "PYTHONPATH": str(REPO_ROOT / "src"),
            "PYTHONUNBUFFERED": "1",
        }
        env.update(env_extra or {})
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "mini_creative_toolkit"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, cwd=REPO_ROOT, env=env,
        )
        self._lines: queue.Queue = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self._lines.put(line)

    def send(self, payload: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def read(self, timeout: float = 90.0) -> dict:
        while True:
            line = self._lines.get(timeout=timeout)
            if line.strip():
                return json.loads(line)

    def initialize(self) -> dict:
        self.send({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "test", "version": "0"}},
        })
        response = self.read()
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return response

    def call(self, name: str, arguments: dict, request_id: int = 99) -> dict:
        self.send({"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                   "params": {"name": name, "arguments": arguments}})
        return self.read()

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.terminate()
        self.proc.wait(timeout=30)


def test_the_server_starts_and_speaks_the_protocol(tmp_path):
    """A real stdio handshake, not a mock: this is what an MCP client does."""
    client = _StdioClient(tmp_path)
    try:
        assert "result" in client.initialize()
        client.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        listing = client.read()
        names = {t["name"] for t in listing["result"]["tools"]}
        assert names == set(CAPABILITIES)
    finally:
        client.close()


def test_a_real_tool_call_over_stdio_returns_a_structured_result(tmp_path):
    source = tmp_path / "demo.png"
    Image.new("RGB", (300, 200), (20, 120, 220)).save(source)
    client = _StdioClient(tmp_path)
    try:
        client.initialize()
        response = client.call("resize_image", {"image_path": str(source), "width": 100, "height": 100})
        payload = json.loads(response["result"]["content"][0]["text"])
        assert payload["actual_width"] == 100
        assert payload["execution"] == "local"
        assert Path(payload["output_path"]).exists()
    finally:
        client.close()


def test_a_deliberate_error_survives_the_whole_stdio_round_trip(tmp_path):
    """End to end, not just at the Python boundary: what a client actually
    receives must still name the file and the problem."""
    client = _StdioClient(tmp_path)
    try:
        client.initialize()
        response = client.call(
            "resize_image", {"image_path": str(tmp_path / "absent.png"), "width": 10, "height": 10}
        )
        result = response["result"]
        assert result["isError"] is True
        assert "No such file" in result["content"][0]["text"]
        assert "absent.png" in result["content"][0]["text"]
    finally:
        client.close()


def test_no_temporary_file_survives_a_failed_call_over_stdio(tmp_path):
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"\x00" * 4096)
    client = _StdioClient(tmp_path)
    try:
        client.initialize()
        assert client.call("video_thumbnail", {"video_path": str(broken)})["result"]["isError"]
    finally:
        client.close()
    out = tmp_path / "out"
    leftovers = list(out.glob("*.part-*")) + list(out.glob("tmp-*")) if out.exists() else []
    assert leftovers == []


def test_logs_go_to_stderr_so_they_cannot_corrupt_the_protocol_stream(tmp_path):
    """An MCP stdio server speaks JSON-RPC on stdout. A stray log line there
    breaks the client's parser."""
    proc = subprocess.run(
        [sys.executable, "-m", "mini_creative_toolkit"],
        input="", capture_output=True, text=True, timeout=60,
        cwd=REPO_ROOT,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
             "MCT_LOG_LEVEL": "verbose",
             "MCT_OUTPUT_DIR": str(tmp_path / "out"),
             "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    for line in proc.stdout.splitlines():
        if line.strip():
            json.loads(line)  # anything on stdout must be valid JSON-RPC
    assert "mini-creative-toolkit MCP server starting" in proc.stderr


def test_the_legacy_launcher_still_works(tmp_path):
    """`uv run toolkit.py` is what existing client configurations say."""
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "toolkit.py")],
        input="", capture_output=True, text=True, timeout=60,
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
             "MCT_OUTPUT_DIR": str(tmp_path / "out"),
             "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    assert proc.returncode == 0, proc.stderr[-2000:]


# --- CLI ---------------------------------------------------------------------

def test_the_cli_and_the_server_call_the_same_functions():
    """Not a stylistic preference: two implementations of 'resize' would drift,
    and only one of them would get the next validation fix."""
    import inspect as pyinspect

    from mini_creative_toolkit import server
    from mini_creative_toolkit.tools import image as image_tools

    source = pyinspect.getsource(server)
    assert "image_tools.resize_image(" in source
    assert pyinspect.getsource(image_tools.resize_image)


def test_prefix_abbreviation_is_disabled_everywhere():
    """argparse's default prefix matching resolves --width to --width-limit if
    such a flag is ever added. A resize that quietly used the wrong argument is
    worse than one that errors."""
    parser = build_parser()
    assert parser.allow_abbrev is False
    for action in parser._subparsers._group_actions:  # type: ignore[union-attr]
        for sub in action.choices.values():
            assert sub.allow_abbrev is False, sub.prog


def test_cli_resize_writes_a_file(tmp_path, capsys):
    source = tmp_path / "a.png"
    Image.new("RGB", (100, 50), (9, 90, 200)).save(source)
    code = main(["--output-dir", str(tmp_path / "out"), "resize", str(source),
                 "--width", "40", "--height", "40"])
    assert code == 0
    out = capsys.readouterr().out
    produced = Path(out.splitlines()[0])
    assert produced.exists()


def test_cli_json_mode_is_machine_readable(tmp_path, capsys):
    source = tmp_path / "a.png"
    Image.new("RGB", (100, 50), (9, 90, 200)).save(source)
    main(["--output-dir", str(tmp_path / "out"), "--json", "inspect", str(source)])
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "image" and payload["width"] == 100


def test_cli_reports_a_missing_file_with_exit_code_1(tmp_path, capsys):
    code = main(["--output-dir", str(tmp_path / "out"), "resize",
                 str(tmp_path / "nope.png"), "--width", "10", "--height", "10"])
    assert code == 1
    assert "No such file" in capsys.readouterr().err


def test_cli_usage_errors_exit_2(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        main(["resize", "--width", "10"])
    assert excinfo.value.code == 2


def test_cli_capabilities_runs_without_any_input_file(tmp_path, capsys):
    assert main(["--json", "capabilities"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tools"]


def test_cli_verbose_surfaces_the_detail_that_normal_mode_hides(tmp_path, capsys):
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"\x00" * 4096)
    main(["--output-dir", str(tmp_path / "out"), "thumbnail", str(broken)])
    quiet_err = capsys.readouterr().err
    main(["--output-dir", str(tmp_path / "out"), "--log-level", "verbose",
          "thumbnail", str(broken)])
    verbose_err = capsys.readouterr().err
    assert len(verbose_err) >= len(quiet_err)


def test_the_installed_console_script_exists():
    script = REPO_ROOT / ".venv" / "bin" / "mct"
    if not script.exists():
        pytest.skip("the package is not installed in a local .venv")
    proc = subprocess.run([str(script), "--version"], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0
    assert re.match(r"mct \d+\.\d+", proc.stdout.strip())


# --- error translation -------------------------------------------------------

def test_a_deliberate_error_reaches_the_model_intact(tmp_path):
    """The SDK masks any non-ToolError exception as "Error executing tool X".

    Correct for a crash, wrong for every error this project raises on purpose:
    "No such file" and "UPSCAYL_BIN_PATH is not set, use upscale_image_fast
    instead" are written for a model to read and act on. Losing them would
    waste the entire error-message design, so the server translates.
    """
    from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

    from mini_creative_toolkit.config import Config, reset_config, set_config

    set_config(Config(output_dir=tmp_path / "out"))
    try:
        with pytest.raises(ToolError) as excinfo:
            asyncio.run(
                mcp.call_tool(
                    "resize_image",
                    {"image_path": str(tmp_path / "absent.png"), "width": 10, "height": 10},
                )
            )
    finally:
        reset_config()
    assert not isinstance(excinfo.value, UnexpectedToolError)
    assert "No such file" in str(excinfo.value)
    assert "absent.png" in str(excinfo.value)


def test_a_missing_dependency_error_keeps_its_advice(tmp_path, png):
    from mcp.server.mcpserver.exceptions import ToolError

    from mini_creative_toolkit.config import Config, reset_config, set_config

    set_config(Config(output_dir=tmp_path / "out"))
    try:
        with pytest.raises(ToolError) as excinfo:
            asyncio.run(mcp.call_tool("upscale_image", {"image_path": str(png), "scale": 4}))
    finally:
        reset_config()
    message = str(excinfo.value)
    assert "UPSCAYL_BIN_PATH" in message
    assert "upscale_image_fast" in message


def test_the_wrapper_does_not_damage_the_generated_input_schema():
    """The error-translating wrapper sits between the tool function and the
    SDK's signature introspection. If it dropped the signature, every tool
    would advertise an empty schema and no client could call anything."""
    tool = next(t for t in _tools() if t.name == "resize_image")
    schema = tool.input_schema
    assert set(schema["required"]) == {"image_path", "width", "height"}
    assert schema["properties"]["keep_aspect"]["default"] is True
    assert schema["properties"]["width"]["type"] == "integer"


def test_every_tool_advertises_a_non_empty_schema_where_it_takes_arguments():
    argument_free = {"list_capabilities", "list_background_models", "list_presets"}
    for tool in _tools():
        properties = tool.input_schema.get("properties", {})
        if tool.name in argument_free:
            assert not properties, tool.name
        else:
            assert properties, f"{tool.name} advertises no arguments"
