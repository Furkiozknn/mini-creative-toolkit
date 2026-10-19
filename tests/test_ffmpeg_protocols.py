"""ffmpeg and ffprobe may open local files only - not URLs, not pipes.

A playlist or concat list names *other* inputs, and ffmpeg opens them with
whatever protocol they spell. Without a whitelist, a hostile ``.m3u8`` makes a
tool that reports ``network: none`` connect out, and it does so during the
ffprobe call that runs before the playlist is recognised and refused.

The first two tests inspect the argv and need no ffmpeg; the rest run the real
binaries against a listening socket and skip themselves without ffmpeg, like
the other video tests.
"""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path

import pytest

from helpers import needs_ffmpeg

from mini_creative_toolkit.config import Config
from mini_creative_toolkit.engines import ffmpeg
from mini_creative_toolkit.errors import ExternalToolError, InvalidInputError
from mini_creative_toolkit.media_info import describe


def _capture_commands(monkeypatch) -> list[list[str]]:
    seen: list[list[str]] = []

    def fake_run(command, **kwargs):
        seen.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr("mini_creative_toolkit.engines.ffmpeg.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("mini_creative_toolkit.engines.ffmpeg.subprocess.run", fake_run)
    return seen


def test_every_ffmpeg_input_is_restricted_to_local_files(monkeypatch, tmp_path):
    seen = _capture_commands(monkeypatch)
    a, b, out = str(tmp_path / "a.mp4"), str(tmp_path / "b.png"), str(tmp_path / "o.gif")
    ffmpeg.run_ffmpeg(["-ss", "00:00:00", "-i", a, "-i", b, "-lavfi", "paletteuse", out], Config(output_dir=tmp_path))
    (command,) = seen
    inputs = [i for i, arg in enumerate(command) if arg == "-i"]
    assert len(inputs) == 2
    for i in inputs:
        assert command[i - 2:i] == ["-protocol_whitelist", "file"], command


def test_ffprobe_is_restricted_to_local_files(monkeypatch, tmp_path):
    seen = _capture_commands(monkeypatch)
    target = tmp_path / "a.mp4"
    ffmpeg.probe(target, Config(output_dir=tmp_path))
    (command,) = seen
    at = command.index("-protocol_whitelist")
    assert command[at + 1] == "file"
    assert at < command.index(str(target)), "the option must come before the input"


# --- Against the real binaries ------------------------------------------------


@pytest.fixture
def listener():
    """A TCP port on loopback that records whether anything connected to it."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)
    yield sock
    sock.close()


def _connected(sock: socket.socket) -> bool:
    sock.setblocking(False)
    try:
        conn, _ = sock.accept()
    except (BlockingIOError, OSError):
        return False
    conn.close()
    return True


def _hostile_hls(tmp_path: Path, port: int) -> Path:
    playlist = tmp_path / "hostile.m3u8"
    playlist.write_text(
        "#EXTM3U\n#EXT-X-TARGETDURATION:3\n#EXTINF:3,\n"
        f"http://127.0.0.1:{port}/segment.ts\n#EXT-X-ENDLIST\n",
        encoding="utf-8",
    )
    return playlist


def _hostile_concat(tmp_path: Path, port: int) -> Path:
    listing = tmp_path / "hostile.ffconcat"
    listing.write_text(
        f"ffconcat version 1.0\nfile 'http://127.0.0.1:{port}/segment.ts'\n",
        encoding="utf-8",
    )
    return listing


def _short_timeouts(tmp_path: Path) -> Config:
    # Without the whitelist ffmpeg connects and then waits for an answer the
    # listener never sends; a short timeout keeps a regression from hanging.
    return Config(output_dir=tmp_path / "out", subprocess_timeout_seconds=20.0)


@needs_ffmpeg
def test_inspecting_a_hostile_playlist_makes_no_connection(tmp_path, listener):
    playlist = _hostile_hls(tmp_path, listener.getsockname()[1])
    with pytest.raises(InvalidInputError):
        describe(playlist, _short_timeouts(tmp_path))
    assert not _connected(listener), "ffprobe opened the playlist's http:// segment"


@needs_ffmpeg
@pytest.mark.parametrize("build, extra", [
    (_hostile_hls, []),
    # -safe 0 lifts the concat demuxer's own URL check, so only the
    # whitelist stands between the list and the network.
    (_hostile_concat, ["-f", "concat", "-safe", "0"]),
])
def test_ffmpeg_will_not_follow_a_hostile_input_onto_the_network(tmp_path, listener, build, extra):
    source = build(tmp_path, listener.getsockname()[1])
    out = tmp_path / "frame.png"
    try:
        ffmpeg.run_ffmpeg([*extra, "-i", str(source), "-frames:v", "1", str(out)], _short_timeouts(tmp_path))
    except ExternalToolError:
        pass
    assert not _connected(listener), "ffmpeg opened an http:// input named inside a local file"
