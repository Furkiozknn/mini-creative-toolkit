"""Capabilities, configuration, and the claims the server makes about itself."""

from __future__ import annotations

import pytest

from mini_creative_toolkit.capabilities import (
    CAPABILITIES,
    ExecutionMode,
    NetworkNeed,
    probe_environment,
    readiness,
)
from mini_creative_toolkit.config import Config
from mini_creative_toolkit.errors import InvalidInputError
from mini_creative_toolkit.tools.background import list_background_models
from mini_creative_toolkit.tools.inspect import list_capabilities
from mini_creative_toolkit.tools.presets import list_presets


def test_exactly_one_tool_is_hosted():
    """The project's central claim, asserted rather than merely written down.

    If a second network-using tool is ever added, this fails and forces the
    README's 'one tool leaves the machine' line to be updated with it.
    """
    hosted = [c.name for c in CAPABILITIES.values() if c.execution is ExecutionMode.HOSTED]
    assert hosted == ["generate_image_free"]


def test_no_local_tool_claims_to_require_the_network():
    for cap in CAPABILITIES.values():
        if cap.execution is ExecutionMode.LOCAL:
            assert cap.network is not NetworkNeed.REQUIRED, cap.name


def test_only_upscale_image_requires_a_gpu():
    from mini_creative_toolkit.capabilities import GpuNeed

    required = [c.name for c in CAPABILITIES.values() if c.gpu is GpuNeed.REQUIRED]
    assert required == ["upscale_image"]


def test_every_tool_that_shells_out_declares_its_binaries():
    """Either as always-required or as needed-for-some-inputs, but declared."""
    for cap in CAPABILITIES.values():
        if cap.uses_subprocess:
            assert cap.external_binaries or cap.conditional_binaries, (
                f"{cap.name} shells out but declares no binary"
            )


def test_the_hosted_tool_names_its_service_and_says_it_is_not_deterministic():
    cap = CAPABILITIES["generate_image_free"]
    assert cap.external_service == "Pollinations.ai"
    assert cap.deterministic is False
    footer = cap.description_footer()
    assert "hosted" in footer and "Pollinations.ai" in footer


def test_readiness_reports_blockers_rather_than_silently_failing_later(config):
    report = readiness(config)
    assert report["resize_image"]["ready"] is True
    upscale = report["upscale_image"]
    if not upscale["ready"]:
        assert any("UPSCAYL" in b or "GPU" in b for b in upscale["blockers"])


def test_list_capabilities_covers_every_registered_tool(config):
    payload = list_capabilities(config)
    assert {t["tool"] for t in payload["tools"]} == set(CAPABILITIES)
    assert payload["limits"]["MCT_MAX_INPUT_MB"] == config.max_input_mb


def test_list_capabilities_does_not_claim_to_be_a_sandbox(config):
    notes = " ".join(list_capabilities(config)["notes"]).lower()
    assert "not a sandbox" in notes


def test_probe_reports_what_this_machine_actually_has(config):
    env = probe_environment(config)
    assert set(env) >= {"ffmpeg", "ffprobe", "discrete_gpu", "image_write_formats"}
    assert isinstance(env["discrete_gpu_reason"], str) and env["discrete_gpu_reason"]


def test_gpu_detection_can_be_forced_both_ways(monkeypatch, config):
    monkeypatch.setenv("MCT_FORCE_GPU", "1")
    assert probe_environment(config)["discrete_gpu"] is True
    monkeypatch.delenv("MCT_FORCE_GPU")
    monkeypatch.setenv("MCT_FORCE_NO_GPU", "1")
    assert probe_environment(config)["discrete_gpu"] is False


def test_image_format_support_is_probed_not_assumed(config):
    """AVIF depends on how Pillow was built. Claiming support this install does
    not have turns a clear error into a confusing one."""
    formats = probe_environment(config)["image_write_formats"]
    assert formats["png"] is True and formats["jpeg"] is True
    assert isinstance(formats["avif"], bool)


def test_unverified_model_licences_say_so_rather_than_guessing():
    payload = list_background_models()
    for model in payload["models"]:
        if not model["license_verified"]:
            assert model["license"] == "not verified"


def test_the_non_commercial_model_is_labelled_as_such():
    payload = list_background_models()
    bria = next(m for m in payload["models"] if m["model"] == "bria-rmbg")
    assert "non-commercial" in bria["license"].lower()
    assert payload["default"] == "u2net"


def test_the_default_model_is_never_rembgs_own_default():
    notes = " ".join(list_background_models()["notes"])
    assert "never falls back to rembg's own internal default" in notes


def test_presets_carry_their_disclaimer():
    payload = list_presets()
    assert "not a guarantee" in payload["disclaimer"]
    assert payload["image"]["square"] == {"width": 1080, "height": 1080}


def test_a_preset_can_be_overridden_from_the_environment(monkeypatch):
    monkeypatch.setenv("MCT_PRESETS_IMAGE_SQUARE", "1200x1200")
    assert list_presets()["image"]["square"] == {"width": 1200, "height": 1200}


def test_a_malformed_preset_override_is_rejected(monkeypatch):
    monkeypatch.setenv("MCT_PRESETS_IMAGE_SQUARE", "huge")
    with pytest.raises(InvalidInputError):
        list_presets()


def test_config_defaults_need_no_environment():
    assert Config.from_env({}).max_input_mb > 0


def test_config_reads_every_documented_variable():
    cfg = Config.from_env(
        {
            "MCT_MAX_INPUT_MB": "12",
            "MCT_MAX_IMAGE_PIXELS": "5000",
            "MCT_MAX_VIDEO_DURATION": "30",
            "MCT_MAX_BATCH_ITEMS": "7",
            "MCT_BATCH_CONCURRENCY": "3",
            "MCT_LOG_LEVEL": "verbose",
            "MCT_HTTP_TIMEOUT": "5",
            "MCT_LEGACY_STRING_RESULTS": "true",
        }
    )
    assert cfg.max_input_mb == 12
    assert cfg.max_image_pixels == 5000
    assert cfg.max_video_duration_seconds == 30
    assert cfg.max_batch_items == 7
    assert cfg.batch_concurrency == 3
    assert cfg.verbose is True
    assert cfg.http_timeout_seconds == 5
    assert cfg.legacy_string_results is True


@pytest.mark.parametrize(
    "env",
    [
        {"MCT_MAX_INPUT_MB": "lots"},
        {"MCT_MAX_BATCH_ITEMS": "-3"},
        {"MCT_LOG_LEVEL": "shouty"},
        {"MCT_LEGACY_STRING_RESULTS": "maybe"},
        {"MCT_ALLOWED_ROOTS": "/definitely/not/here"},
    ],
)
def test_bad_configuration_fails_loudly_at_startup(env):
    with pytest.raises(InvalidInputError):
        Config.from_env(env)


def test_allowed_roots_accept_several_entries(tmp_path):
    import os

    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    cfg = Config.from_env({"MCT_ALLOWED_ROOTS": os.pathsep.join([str(a), str(b)])})
    assert set(cfg.allowed_roots) == {a.resolve(), b.resolve()}


def test_a_partial_dependency_is_a_limitation_not_a_blocker(monkeypatch, config):
    """inspect_media handles every image with no ffprobe at all. Reporting it
    as 'not ready' when ffmpeg is absent would be a broader claim than the
    truth, and would send a caller looking for a problem they do not have."""
    import mini_creative_toolkit.capabilities as caps

    monkeypatch.setattr(caps.shutil, "which", lambda name: None)
    report = caps.readiness(config)

    assert report["inspect_media"]["ready"] is True
    assert report["inspect_media"]["limitations"]
    assert "video and audio" in report["inspect_media"]["limitations"][0]

    # A tool that genuinely cannot run is still reported as blocked.
    assert report["video_thumbnail"]["ready"] is False
    assert "ffmpeg is not on PATH" in report["video_thumbnail"]["blockers"]


def test_conditional_binaries_are_declared_separately_from_required_ones():
    inspect_cap = CAPABILITIES["inspect_media"]
    assert inspect_cap.external_binaries == ()
    assert "ffprobe" in inspect_cap.conditional_binaries
    assert "some inputs" in inspect_cap.description_footer()

    thumbnail_cap = CAPABILITIES["video_thumbnail"]
    assert "ffmpeg" in thumbnail_cap.external_binaries
    assert thumbnail_cap.conditional_binaries == ()
