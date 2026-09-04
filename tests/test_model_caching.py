"""Loaded models are reused across calls - the difference between a batch of
twenty taking twenty seconds and taking six minutes."""

from __future__ import annotations

import threading

import pytest
from PIL import Image

from mini_creative_toolkit.config import Config, set_config
from mini_creative_toolkit.engines import background, images
from mini_creative_toolkit.tools.background import remove_background
from mini_creative_toolkit.tools.upscale import upscale_image_fast


def test_fsrcnn_network_is_loaded_once_per_scale(config, tmp_path):
    source = tmp_path / "s.png"
    Image.new("RGB", (24, 24), (5, 5, 5)).save(source)
    assert images._FSRCNN_ENGINES == {}
    upscale_image_fast(str(source), 2)
    first = images._FSRCNN_ENGINES[2][0]
    upscale_image_fast(str(source), 2)
    upscale_image_fast(str(source), 3)
    assert images._FSRCNN_ENGINES[2][0] is first
    assert set(images._FSRCNN_ENGINES) == {2, 3}


def test_fsrcnn_cache_can_be_disabled(config, tmp_path):
    set_config(Config(output_dir=config.output_dir, cache_models=False))
    source = tmp_path / "s.png"
    Image.new("RGB", (16, 16), (5, 5, 5)).save(source)
    upscale_image_fast(str(source), 2)
    assert images._FSRCNN_ENGINES == {}


def test_fsrcnn_engine_is_shared_safely_across_threads(config, tmp_path):
    """Batch workers hit the same network concurrently; the per-engine lock
    is what keeps OpenCV's DNN from being entered re-entrantly."""
    source = tmp_path / "s.png"
    Image.new("RGB", (20, 20), (9, 9, 9)).save(source)
    errors: list[BaseException] = []

    def work():
        try:
            upscale_image_fast(str(source), 2)
        except BaseException as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=work) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(images._FSRCNN_ENGINES) == 1


def test_rembg_session_is_built_once_per_model(config, monkeypatch, tmp_path):
    import rembg

    built: list[str] = []

    def fake_new_session(name):
        built.append(name)
        return f"session-{name}"

    monkeypatch.setattr(rembg, "new_session", fake_new_session)
    monkeypatch.setattr(rembg, "remove", lambda data, session=None: data)

    source = tmp_path / "s.png"
    Image.new("RGB", (8, 8), (1, 2, 3)).save(source)
    remove_background(str(source))
    remove_background(str(source))
    remove_background(str(source), model="u2netp")
    remove_background(str(source))
    assert built == ["u2net", "u2netp"]


def test_rembg_cache_respects_the_opt_out(config, monkeypatch, tmp_path):
    import rembg

    set_config(Config(output_dir=config.output_dir, cache_models=False))
    built: list[str] = []
    monkeypatch.setattr(rembg, "new_session", lambda name: built.append(name) or "s")
    monkeypatch.setattr(rembg, "remove", lambda data, session=None: data)
    source = tmp_path / "s.png"
    Image.new("RGB", (8, 8), (1, 2, 3)).save(source)
    remove_background(str(source))
    remove_background(str(source))
    assert built == ["u2net", "u2net"]


def test_a_failed_session_build_is_not_cached(config, monkeypatch, tmp_path):
    """Offline on first use must not poison every later call."""
    import rembg

    from mini_creative_toolkit.errors import ModelUnavailableError

    calls = {"n": 0}

    def flaky(name):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("no network")
        return "session"

    monkeypatch.setattr(rembg, "new_session", flaky)
    monkeypatch.setattr(rembg, "remove", lambda data, session=None: data)
    source = tmp_path / "s.png"
    Image.new("RGB", (8, 8), (1, 2, 3)).save(source)
    with pytest.raises(ModelUnavailableError):
        remove_background(str(source))
    remove_background(str(source))
    assert calls["n"] == 2
    assert background._SESSIONS == {"u2net": "session"}
