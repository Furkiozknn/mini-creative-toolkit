"""Inline previews: a thumbnail and a resource_link next to the unchanged
result, for every tool that produced an image - through the real MCP call
path (mcp.call_tool), not by calling the functions directly."""
from __future__ import annotations

import asyncio
import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from mini_creative_toolkit import previews
from mini_creative_toolkit.server import mcp


def _call(name: str, args: dict):
    return asyncio.run(mcp.call_tool(name, args))


def _png(path: Path, size=(1600, 1200), mode="RGB", colour=(200, 30, 30)) -> Path:
    Image.new(mode, size, colour if mode == "RGB" else (*colour, 128)).save(path)
    return path


def _decoded(image_content) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(image_content.data)))


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    from mini_creative_toolkit import config

    d = tmp_path / "out"
    d.mkdir()
    monkeypatch.setenv("MCT_OUTPUT_DIR", str(d))
    monkeypatch.delenv(previews.PREVIEW_ENV, raising=False)
    if hasattr(config, "reset_config"):
        config.reset_config()
    elif hasattr(config.get_config, "cache_clear"):
        config.get_config.cache_clear()
    yield d
    if hasattr(config, "reset_config"):
        config.reset_config()
    elif hasattr(config.get_config, "cache_clear"):
        config.get_config.cache_clear()


def test_resize_returns_text_thumbnail_and_link(tmp_path, out_dir):
    src = _png(tmp_path / "big.png")
    result = _call("resize_image", {"image_path": str(src), "width": 800, "height": 800})

    assert not result.is_error
    text, image, link = result.content
    data = json.loads(text.text)
    assert data["output_path"] and data["operation"] == "resize_image"
    assert result.structured_content == {"result": data}, "same structuredContent as before"
    thumb = _decoded(image)
    assert max(thumb.size) <= previews.PREVIEW_MAX_SIDE
    assert image.mime_type == "image/jpeg"
    assert link.type == "resource_link" and link.mime_type == "image/png"
    assert link.uri == Path(data["output_path"]).resolve().as_uri()


def test_the_output_file_itself_is_untouched(tmp_path, out_dir):
    src = _png(tmp_path / "big.png")
    result = _call("resize_image", {"image_path": str(src), "width": 800, "height": 800})
    out = Path(json.loads(result.content[0].text)["output_path"])
    with Image.open(out) as img:
        assert max(img.size) == 800, "the preview is a copy; the output keeps its real size"


def test_transparency_is_previewed_as_png(tmp_path, out_dir):
    src = _png(tmp_path / "alpha.png", size=(300, 200), mode="RGBA")
    result = _call("strip_metadata", {"image_path": str(src)})
    image = result.content[1]
    assert image.mime_type == "image/png"
    assert _decoded(image).mode == "RGBA"


def test_tools_without_an_image_output_are_unchanged(tmp_path, out_dir):
    src = _png(tmp_path / "a.png", size=(64, 64))
    result = _call("inspect_media", {"path": str(src)})
    assert [c.type for c in result.content] == ["text"]
    result = _call("compare_images", {"image_a": str(src), "image_b": str(src)})
    assert [c.type for c in result.content] == ["text"]


def test_previews_can_be_switched_off(tmp_path, out_dir, monkeypatch):
    monkeypatch.setenv(previews.PREVIEW_ENV, "0")
    src = _png(tmp_path / "big.png", size=(200, 200))
    result = _call("resize_image", {"image_path": str(src), "width": 100, "height": 100})
    assert [c.type for c in result.content] == ["text"]
    assert result.structured_content["result"]["output_path"]


def test_errors_are_still_tool_errors(tmp_path, out_dir):
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError, match="No such file|not found|does not exist"):
        _call("resize_image", {"image_path": str(tmp_path / "missing.png"), "width": 10, "height": 10})


def test_direct_calls_keep_returning_the_plain_dict(tmp_path, out_dir):
    from mini_creative_toolkit import server

    src = _png(tmp_path / "big.png", size=(200, 200))
    result = server.resize_image(str(src), 100, 100)
    assert isinstance(result, dict) and result["output_path"]


def test_an_unreadable_image_gets_no_preview_but_the_result_survives(tmp_path):
    fake = tmp_path / "broken.png"
    fake.write_bytes(b"not really a png")
    assert previews.output_image({"output_path": str(fake)}) == fake
    assert previews.thumbnail(fake) is None


@pytest.mark.parametrize("value", [None, "x.mp4", 42])
def test_non_image_outputs_are_ignored(tmp_path, value):
    if value == "x.mp4":
        (tmp_path / "x.mp4").write_bytes(b"\x00")
        value = str(tmp_path / "x.mp4")
    assert previews.output_image({"output_path": value}) is None
    assert previews.output_image("legacy string result") is None


def test_gif_preview_uses_the_first_frame(tmp_path):
    frames = [Image.new("RGB", (100, 80), c) for c in ((255, 0, 0), (0, 255, 0))]
    gif = tmp_path / "a.gif"
    frames[0].save(gif, save_all=True, append_images=frames[1:])
    thumb = previews.thumbnail(gif)
    assert thumb is not None and _decoded(thumb).size == (100, 80)
