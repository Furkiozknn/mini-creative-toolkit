"""Unit tests for the validators - the layer that stands between an MCP
argument and an argv entry."""

from __future__ import annotations

import pytest

from mini_creative_toolkit.errors import InvalidInputError
from mini_creative_toolkit.validation import (
    require_choice,
    require_name,
    require_positive_int,
    require_positive_number,
    require_ratio,
    require_text,
    require_timestamp,
)


@pytest.mark.parametrize(
    "value,expected",
    [("00:00:05", "00:00:05"), ("1:02:03.5", "1:02:03.5"), ("30", "30"), ("2:30", "2:30")],
)
def test_timestamp_accepts_real_timestamps(value, expected):
    assert require_timestamp(value) == expected


def test_timestamp_accepts_a_number_of_seconds():
    assert require_timestamp(2.5).startswith("2.5")


@pytest.mark.parametrize(
    "value",
    [
        "-ss",                      # would be read by ffmpeg as an option
        "-i /etc/passwd",
        "00:00:05; rm -rf /",       # shell metacharacters
        "$(id)",
        "`id`",
        "00:00:05 && curl evil",
        "../../etc/passwd",
        "00:00:05\n-y",             # newline, in case anything ever splits on it
        "",
        "  ",
        "99:99:99:99",
        None,
        [],
    ],
)
def test_timestamp_rejects_anything_that_is_not_a_timestamp(value):
    """None of these can be sanitised into something safe, so all are refused.

    ffmpeg's own -ss parser accepts far more than this grammar; narrowing it
    here is what guarantees the value cannot be mistaken for an option.
    """
    with pytest.raises(InvalidInputError):
        require_timestamp(value)


def test_timestamp_rejects_negative_seconds():
    with pytest.raises(InvalidInputError):
        require_timestamp(-5)


@pytest.mark.parametrize(
    "value",
    ["../evil", "a/b", "a;b", "-model", "with space", "", "x" * 65, "mo.del", None, 5],
)
def test_name_rejects_anything_that_could_traverse_or_look_like_a_flag(value):
    with pytest.raises(InvalidInputError):
        require_name(value, "model")


def test_name_accepts_real_model_names():
    assert require_name("upscayl-standard-4x", "model") == "upscayl-standard-4x"
    assert require_name("isnet-general-use", "model") == "isnet-general-use"


def test_positive_int_accepts_an_integral_float_because_json_has_no_int_type():
    assert require_positive_int(4.0, "scale") == 4


@pytest.mark.parametrize("value", [0, -1, 3.5, True, "4", None])
def test_positive_int_rejects_the_rest(value):
    with pytest.raises(InvalidInputError):
        require_positive_int(value, "scale")


def test_positive_int_enforces_a_maximum():
    with pytest.raises(InvalidInputError):
        require_positive_int(10_000, "width", maximum=4096)


def test_positive_number_rejects_zero_and_negatives():
    assert require_positive_number(1.5, "duration") == 1.5
    for bad in (0, -0.1, "1", True):
        with pytest.raises(InvalidInputError):
            require_positive_number(bad, "duration")


def test_ratio_bounds():
    assert require_ratio(0.0, "opacity") == 0.0
    assert require_ratio(1.0, "opacity") == 1.0
    for bad in (-0.01, 1.01, "0.5", None):
        with pytest.raises(InvalidInputError):
            require_ratio(bad, "opacity")


def test_choice_is_case_insensitive_but_closed():
    assert require_choice("WEB", "goal", {"web", "quality"}) == "web"
    with pytest.raises(InvalidInputError):
        require_choice("everything", "goal", {"web", "quality"})


@pytest.mark.parametrize(
    "value", ["a\x1b[31mred", "a\x00b", "line\nbreak", "tab\there", "bell\x07"]
)
def test_text_rejects_control_characters_rather_than_stripping_them(value):
    """A caption carrying an ANSI escape means something is wrong upstream.
    Drawing a silently-mangled version of it would hide that."""
    with pytest.raises(InvalidInputError):
        require_text(value, "text")


def test_text_accepts_unicode_and_punctuation():
    assert require_text("© Furki Özkan 2026 — «tamam»", "text")


def test_text_enforces_a_length_limit():
    with pytest.raises(InvalidInputError):
        require_text("x" * 501, "text", max_length=500)
