"""Batch processing: isolation, bounds, and no accidental overwrites."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mini_creative_toolkit.config import Config
from mini_creative_toolkit.errors import InvalidInputError, ResourceLimitError
from mini_creative_toolkit.tools.batch import batch_process


@pytest.fixture
def many_images(tmp_path):
    paths = []
    for i in range(6):
        p = tmp_path / f"img{i}.png"
        Image.new("RGB", (80, 60), (i * 30, 40, 200)).save(p)
        paths.append(str(p))
    return paths


def test_a_batch_processes_every_file(config, many_images):
    result = batch_process(many_images, "resize", {"width": 20, "height": 20})
    assert result["total"] == result["succeeded"] == 6
    assert result["failed"] == 0
    for entry in result["results"]:
        assert Path(entry["output_path"]).exists()


def test_one_bad_file_does_not_abort_the_batch(config, many_images, tmp_path):
    """This is the property the whole design exists for."""
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"definitely not a PNG")
    result = batch_process(many_images + [str(broken)], "resize", {"width": 20, "height": 20})
    assert result["succeeded"] == 6
    assert result["failed"] == 1
    assert result["errors"][0]["input"].endswith("broken.png")
    assert "message" in result["errors"][0]


def test_errors_carry_the_original_index_so_results_stay_alignable(config, many_images, tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"nope")
    mixed = [many_images[0], str(broken), many_images[1]]
    result = batch_process(mixed, "resize", {"width": 10, "height": 10})
    assert result["errors"][0]["index"] == 1
    assert [r["index"] for r in result["results"]] == [0, 2]


def test_outputs_never_collide_even_under_concurrency(config, many_images):
    result = batch_process(many_images, "resize", {"width": 20, "height": 20})
    outputs = [entry["output_path"] for entry in result["results"]]
    assert len(set(outputs)) == len(outputs)


def test_nothing_is_written_over_an_input(config, many_images):
    before = {p: Path(p).read_bytes() for p in many_images}
    batch_process(many_images, "strip_metadata", {})
    for path, content in before.items():
        assert Path(path).read_bytes() == content


def test_an_explicit_output_path_is_refused_rather_than_ignored(config, many_images, tmp_path):
    """Every item would write to the same file. Silently ignoring the option
    would look like it worked."""
    with pytest.raises(InvalidInputError, match="output_path"):
        batch_process(
            many_images, "resize",
            {"width": 20, "height": 20, "output_path": str(tmp_path / "one.png")},
        )


def test_an_unknown_operation_lists_the_real_ones(config, many_images):
    with pytest.raises(InvalidInputError) as excinfo:
        batch_process(many_images, "enhance", {})
    assert "resize" in excinfo.value.message


def test_missing_required_options_are_named(config, many_images):
    with pytest.raises(InvalidInputError, match="width"):
        batch_process(many_images, "resize", {})


def test_the_batch_item_limit_names_itself(config, many_images):
    tight = Config(output_dir=config.output_dir, max_batch_items=3)
    with pytest.raises(ResourceLimitError) as excinfo:
        batch_process(many_images, "resize", {"width": 10, "height": 10}, config=tight)
    assert excinfo.value.limit_name == "MCT_MAX_BATCH_ITEMS"


def test_cpu_heavy_operations_get_a_lower_concurrency_cap(config, many_images):
    """Saturating every core with ONNX sessions is how a 'batch of 20' ends up
    slower than doing them one at a time."""
    with pytest.raises(ResourceLimitError) as excinfo:
        batch_process(many_images, "remove_background", {}, concurrency=8, config=config)
    assert excinfo.value.limit_name == "MCT_HEAVY_BATCH_CONCURRENCY"
    assert excinfo.value.limit_value == config.heavy_batch_concurrency


def test_concurrency_within_the_cap_is_accepted(config, many_images):
    result = batch_process(many_images, "resize", {"width": 10, "height": 10}, concurrency=2)
    assert result["concurrency"] == 2
    assert result["succeeded"] == 6


@pytest.mark.parametrize("bad", [0, -1, "two", 1.5])
def test_nonsense_concurrency_is_rejected(config, many_images, bad):
    with pytest.raises(InvalidInputError):
        batch_process(many_images, "resize", {"width": 10, "height": 10}, concurrency=bad)


def test_a_batch_of_conversions_reports_size_changes(config, many_images):
    result = batch_process(many_images, "convert_format", {"target_format": "webp"})
    assert result["succeeded"] == 6
    assert all("size_change_percent" in entry for entry in result["results"])


def test_a_batch_leaves_no_partial_files_behind(config, many_images, tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"nope")
    batch_process(many_images + [str(broken)], "optimize", {"goal": "web"})
    assert list(config.output_dir.glob("*.part-*")) == []
