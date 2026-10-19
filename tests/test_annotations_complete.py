"""The full set of MCP behaviour hints, derived from the capability table and
from each tool's own signature - never written by hand per tool."""
from __future__ import annotations

import asyncio
import inspect

from mini_creative_toolkit import server
from mini_creative_toolkit.capabilities import CAPABILITIES
from mini_creative_toolkit.server import TITLES, mcp


def _tools():
    return asyncio.run(mcp.list_tools())


def test_every_tool_has_a_title_in_both_places():
    for tool in _tools():
        assert TITLES.get(tool.name), tool.name
        assert tool.title == TITLES[tool.name]
        assert tool.annotations.title == TITLES[tool.name]
    assert set(TITLES) == {t.name for t in _tools()}, "no stale titles"


def test_destructive_exactly_when_the_tool_can_replace_a_file():
    for tool in _tools():
        cap = CAPABILITIES[tool.name]
        accepts_overwrite = "overwrite" in tool.input_schema.get("properties", {})
        if cap.writes_files:
            assert tool.annotations.destructive_hint is accepts_overwrite, tool.name
        else:
            assert tool.annotations.destructive_hint is None, tool.name


def test_idempotent_exactly_when_read_only():
    for tool in _tools():
        assert tool.annotations.idempotent_hint is tool.annotations.read_only_hint, tool.name


def test_known_cases():
    by_name = {t.name: t.annotations for t in _tools()}
    assert by_name["resize_image"].destructive_hint is True, "overwrite=true replaces a file"
    assert by_name["batch_process"].destructive_hint is False, "batch outputs never collide"
    assert by_name["batch_process"].read_only_hint is False
    assert by_name["compare_images"].read_only_hint is True
    assert by_name["compare_images"].idempotent_hint is True
    assert by_name["list_capabilities"].destructive_hint is None
    assert by_name["generate_image_free"].open_world_hint is True
    assert by_name["generate_image_free"].idempotent_hint is False


def test_the_overwrite_detection_reads_the_real_signature():
    assert "overwrite" in inspect.signature(server.resize_image).parameters
    assert "overwrite" not in inspect.signature(server.batch_process).parameters
