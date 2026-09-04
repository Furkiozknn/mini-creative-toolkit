"""Path handling under hostile input.

These are the tests the brief asks for by name: traversal, shell
metacharacters, long paths, unicode, spaces, quotes, newlines. The point of
each is not that the string is dangerous in itself - none of them ever reach
a shell - but that resolution is predictable and that a configured allowed
root is actually enforced after normalisation, not before it.
"""

from __future__ import annotations

import os

import pytest
from PIL import Image

from mini_creative_toolkit.config import Config
from mini_creative_toolkit.errors import (
    InvalidInputError,
    PathPermissionError,
    ResourceLimitError,
)
from mini_creative_toolkit.paths import (
    OutputManager,
    is_within,
    normalize,
    resolve_input,
    resolve_input_list,
    safe_stem,
)


@pytest.fixture
def rooted(tmp_path):
    """A config whose allowed root is tmp_path/work."""
    work = tmp_path / "work"
    work.mkdir()
    return Config(output_dir=tmp_path / "out", allowed_roots=(work.resolve(),)), work


def test_traversal_is_collapsed_before_the_root_check(rooted):
    config, work = rooted
    (work / "a").mkdir()
    escape = str(work / "a" / ".." / ".." / ".." / "etc" / "passwd")
    with pytest.raises((PathPermissionError, InvalidInputError)):
        resolve_input(escape, config)


@pytest.mark.parametrize("target", ["/etc/passwd", "/etc/../etc/passwd", "~root/.ssh/id_rsa"])
def test_absolute_paths_outside_the_root_are_refused(rooted, target):
    config, _ = rooted
    with pytest.raises((PathPermissionError, InvalidInputError)):
        resolve_input(target, config)


def test_a_symlink_cannot_smuggle_a_file_into_an_allowed_root(rooted):
    """resolve() follows symlinks *before* the root check, so a link planted
    inside the root still resolves to its real location and is refused."""
    config, work = rooted
    link = work / "innocent.png"
    try:
        os.symlink("/etc/hostname", link)
    except OSError:  # pragma: no cover - unusual filesystem
        pytest.skip("symlinks are not supported here")
    with pytest.raises((PathPermissionError, InvalidInputError)):
        resolve_input(str(link), config)


def test_no_root_configured_means_no_root_restriction(tmp_path):
    """The default is documented, not accidental: with MCT_ALLOWED_ROOTS unset
    this is an ordinary local tool with the user's own file permissions.
    SECURITY.md says so rather than implying a sandbox that does not exist."""
    config = Config(output_dir=tmp_path / "out")
    resolved = resolve_input("/etc/hostname", config)
    assert resolved.name == "hostname"


@pytest.mark.parametrize(
    "name",
    [
        "with space.png",
        "with'quote.png",
        'with"doublequote.png',
        "with;semicolon.png",
        "with$dollar.png",
        "with`backtick.png",
        "with|pipe.png",
        "with&amp.png",
        "with*glob.png",
        "with(paren).png",
        "üniçode-ösürgen.png",
        "-leading-dash.png",
    ],
)
def test_awkward_filenames_are_handled_as_data_not_syntax(tmp_path, name):
    """None of these reach a shell - every subprocess call passes an argument
    list - so they must simply work."""
    config = Config(output_dir=tmp_path / "out")
    path = tmp_path / name
    Image.new("RGB", (8, 8), (1, 2, 3)).save(path, format="PNG")
    assert resolve_input(str(path), config) == path.resolve()


def test_a_newline_in_a_filename_is_still_just_a_filename(tmp_path):
    config = Config(output_dir=tmp_path / "out")
    path = tmp_path / "two\nlines.png"
    try:
        Image.new("RGB", (8, 8), (1, 2, 3)).save(path, format="PNG")
    except OSError:  # pragma: no cover
        pytest.skip("this filesystem rejects newlines in names")
    assert resolve_input(str(path), config) == path.resolve()


def test_nul_bytes_are_refused_outright(tmp_path):
    config = Config(output_dir=tmp_path / "out")
    with pytest.raises(InvalidInputError):
        resolve_input("/tmp/evil\x00.png", config)


def test_an_absurdly_long_path_fails_cleanly(tmp_path):
    config = Config(output_dir=tmp_path / "out")
    with pytest.raises((InvalidInputError, PathPermissionError)):
        resolve_input(str(tmp_path / ("x" * 5000 + ".png")), config)


def test_a_directory_is_not_a_file(tmp_path):
    config = Config(output_dir=tmp_path / "out")
    with pytest.raises(InvalidInputError, match="directory"):
        resolve_input(str(tmp_path), config)


def test_a_fifo_is_not_a_regular_file(tmp_path):
    """ffmpeg would block forever on a FIFO, so it is refused up front."""
    config = Config(output_dir=tmp_path / "out")
    fifo = tmp_path / "pipe"
    try:
        os.mkfifo(fifo)
    except (AttributeError, OSError):  # pragma: no cover
        pytest.skip("mkfifo is unavailable here")
    with pytest.raises(InvalidInputError, match="regular file"):
        resolve_input(str(fifo), config)


def test_an_empty_file_is_refused(tmp_path):
    config = Config(output_dir=tmp_path / "out")
    empty = tmp_path / "empty.png"
    empty.touch()
    with pytest.raises(InvalidInputError, match="empty"):
        resolve_input(str(empty), config)


def test_the_input_size_limit_names_itself(tmp_path):
    config = Config(output_dir=tmp_path / "out", max_input_mb=0.001)
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * 5000)
    with pytest.raises(ResourceLimitError) as excinfo:
        resolve_input(str(big), config)
    assert excinfo.value.limit_name == "MCT_MAX_INPUT_MB"
    assert "MCT_MAX_INPUT_MB" in excinfo.value.message


def test_batch_lists_are_bounded(tmp_path):
    config = Config(output_dir=tmp_path / "out", max_batch_items=3)
    paths = []
    for i in range(4):
        p = tmp_path / f"{i}.png"
        Image.new("RGB", (4, 4), (0, 0, 0)).save(p)
        paths.append(str(p))
    with pytest.raises(ResourceLimitError) as excinfo:
        resolve_input_list(paths, config)
    assert excinfo.value.limit_name == "MCT_MAX_BATCH_ITEMS"


def test_is_within_is_not_fooled_by_a_shared_prefix(tmp_path):
    assert not is_within(tmp_path / "workspace-evil", tmp_path / "workspace")
    assert is_within(tmp_path / "workspace" / "a", tmp_path / "workspace")


def test_safe_stem_strips_everything_that_is_not_filename_safe():
    assert safe_stem("../../etc/passwd") == "etc-passwd"
    assert safe_stem("a;b|c") == "a-b-c"
    assert safe_stem("!!!") == "output"


def test_output_names_do_not_collide_under_concurrency(tmp_path):
    """A bare timestamp collides when two batch workers finish in the same
    microsecond; the random suffix is what actually prevents it."""
    manager = OutputManager(Config(output_dir=tmp_path / "out"))
    names = {manager.allocate("x", "png") for _ in range(500)}
    assert len(names) == 500


def test_explicit_output_refuses_to_overwrite_by_default(tmp_path):
    manager = OutputManager(Config(output_dir=tmp_path / "out"))
    target = tmp_path / "existing.png"
    target.write_bytes(b"original")
    with pytest.raises(InvalidInputError, match="overwrite"):
        manager.resolve_explicit(str(target), overwrite=False)
    assert manager.resolve_explicit(str(target), overwrite=True) == target.resolve()
    assert target.read_bytes() == b"original"  # resolving alone changes nothing


def test_a_failed_operation_leaves_no_partial_file(tmp_path):
    manager = OutputManager(Config(output_dir=tmp_path / "out"))
    with pytest.raises(RuntimeError):
        with manager.stage("thing", "png") as staged:
            staged.tmp.write_bytes(b"half a file")
            raise RuntimeError("engine blew up")
    assert list((tmp_path / "out").iterdir()) == []


def test_the_output_size_limit_deletes_the_oversized_file(tmp_path):
    manager = OutputManager(Config(output_dir=tmp_path / "out", max_output_mb=0.001))
    with pytest.raises(ResourceLimitError):
        with manager.stage("thing", "png") as staged:
            staged.tmp.write_bytes(b"x" * 5000)
    assert list((tmp_path / "out").iterdir()) == []


def test_cleanup_removes_partials_from_a_crashed_earlier_run(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "thing.part-abcd.png").write_bytes(b"leftover")
    (out / "real.png").write_bytes(b"keep me")
    manager = OutputManager(Config(output_dir=out))
    assert manager.cleanup_partials() == 1
    assert [p.name for p in out.iterdir()] == ["real.png"]


def test_normalize_expands_user_but_still_returns_an_absolute_path():
    assert normalize("~").is_absolute()
