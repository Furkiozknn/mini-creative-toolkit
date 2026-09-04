"""The hosted tool, exercised entirely against mocked HTTP.

CI must never depend on Pollinations.ai being reachable, and a test suite
that quietly starts making real outbound requests would contradict the
project's central claim. Every request here is served by an httpx
MockTransport; nothing leaves the machine.
"""

from __future__ import annotations

import io

import httpx
import pytest
from PIL import Image

from mini_creative_toolkit.engines import pollinations
from mini_creative_toolkit.errors import InvalidInputError, NetworkError, ResourceLimitError
from mini_creative_toolkit.tools.generate import generate_image_free


def _png_bytes(size=(32, 32)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (12, 34, 56)).save(buffer, format="PNG")
    return buffer.getvalue()


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_a_valid_response_is_decoded_and_saved(config):
    body = _png_bytes()

    def handler(request):
        assert request.url.host == "image.pollinations.ai"
        assert request.url.params["width"] == "256"
        return httpx.Response(200, content=body, headers={"content-type": "image/png"})

    result = generate_image_free("a red square", 256, 256, client=_client(handler))
    assert result["format"] == "PNG"
    assert result["execution"] == "hosted"
    assert result["external_service"] == "Pollinations.ai"
    assert "sent to Pollinations.ai" in result["disclosure"]


def test_the_result_discloses_that_the_prompt_left_the_machine(config):
    def handler(request):
        return httpx.Response(200, content=_png_bytes(), headers={"content-type": "image/png"})

    result = generate_image_free("anything", 64, 64, client=_client(handler))
    assert "third-party" in result["disclosure"]


def test_a_timeout_is_reported_as_a_timeout(config):
    def handler(request):
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(NetworkError, match="did not respond"):
        generate_image_free("x", 64, 64, client=_client(handler))


def test_a_connection_failure_does_not_leak_a_traceback(config):
    def handler(request):
        raise httpx.ConnectError("no route to host", request=request)

    with pytest.raises(NetworkError) as excinfo:
        generate_image_free("x", 64, 64, client=_client(handler))
    assert "Could not reach" in excinfo.value.message
    assert "Traceback" not in excinfo.value.message


@pytest.mark.parametrize("status", [400, 404, 429])
def test_client_errors_are_reported_as_a_rejection(config, status):
    def handler(request):
        return httpx.Response(status, content=b"nope", headers={"content-type": "text/plain"})

    with pytest.raises(NetworkError, match="rejected the request"):
        generate_image_free("x", 64, 64, client=_client(handler))


@pytest.mark.parametrize("status", [500, 502, 503])
def test_server_errors_are_reported_as_the_service_failing(config, status):
    def handler(request):
        return httpx.Response(status, content=b"oops")

    with pytest.raises(NetworkError, match="is failing"):
        generate_image_free("x", 64, 64, client=_client(handler))


@pytest.mark.parametrize("status", [401, 403])
def test_an_auth_response_is_called_out_specifically(config, status):
    """If this endpoint ever starts requiring a key, the error should say that
    plainly rather than looking like a generic failure - and should state that
    nothing else in the toolkit is affected."""
    def handler(request):
        return httpx.Response(status, content=b"denied")

    with pytest.raises(NetworkError) as excinfo:
        generate_image_free("x", 64, 64, client=_client(handler))
    assert "requiring authentication" in excinfo.value.message
    assert "Nothing else in this toolkit depends on it" in excinfo.value.message


def test_an_html_error_page_with_a_200_status_is_not_saved_as_an_image(config):
    """The failure this prevents: a proxy or an error page served with HTTP 200
    used to be written straight to disk as a .jpg."""
    def handler(request):
        return httpx.Response(
            200, content=b"<html><body>Service unavailable</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )

    with pytest.raises(NetworkError, match="not an image"):
        generate_image_free("x", 64, 64, client=_client(handler))
    assert list(config.output_dir.glob("generated-*")) == []


def test_a_correct_content_type_with_a_corrupt_body_is_still_refused(config):
    """A correct Content-Type is a claim; decoding is evidence."""
    def handler(request):
        return httpx.Response(
            200, content=b"\xff\xd8\xff" + b"truncated", headers={"content-type": "image/jpeg"}
        )

    with pytest.raises(NetworkError, match="not a decodable image"):
        generate_image_free("x", 64, 64, client=_client(handler))


def test_an_empty_body_is_refused(config):
    def handler(request):
        return httpx.Response(200, content=b"", headers={"content-type": "image/png"})

    with pytest.raises(NetworkError, match="empty body"):
        generate_image_free("x", 64, 64, client=_client(handler))


def test_an_oversized_response_is_aborted_and_nothing_is_written(config):
    from mini_creative_toolkit.config import Config

    tight = Config(output_dir=config.output_dir, max_download_mb=0.001)

    def handler(request):
        return httpx.Response(
            200, content=b"\x89PNG" + b"x" * 200_000, headers={"content-type": "image/png"}
        )

    with pytest.raises(ResourceLimitError) as excinfo:
        generate_image_free("x", 64, 64, config=tight, client=_client(handler))
    assert excinfo.value.limit_name == "MCT_MAX_DOWNLOAD_MB"
    assert list(config.output_dir.glob("generated-*")) == []


def test_a_redirect_is_followed(config):
    def handler(request):
        if request.url.path.startswith("/prompt/"):
            return httpx.Response(302, headers={"location": "https://cdn.example/img.png"})
        return httpx.Response(200, content=_png_bytes(), headers={"content-type": "image/png"})

    assert generate_image_free("x", 64, 64, client=_client(handler))["format"] == "PNG"


def test_the_prompt_is_url_encoded_not_interpolated():
    """Nothing about a prompt should be able to change the request path."""
    url = pollinations.build_url("../../admin?x=1&y=2 #frag")
    assert url.startswith("https://image.pollinations.ai/prompt/")
    for raw in ("../", "?", "&", "#", " "):
        assert raw not in url.removeprefix("https://image.pollinations.ai/prompt/")


def test_an_empty_or_oversized_prompt_never_reaches_the_network(config):
    def handler(request):  # pragma: no cover - must not be called
        raise AssertionError("a request was made despite invalid input")

    for bad in ("", "   ", "x" * 1001):
        with pytest.raises(InvalidInputError):
            generate_image_free(bad, 64, 64, client=_client(handler))


def test_absurd_dimensions_never_reach_the_network(config):
    def handler(request):  # pragma: no cover
        raise AssertionError("a request was made despite invalid input")

    with pytest.raises(InvalidInputError):
        generate_image_free("x", 100000, 64, client=_client(handler))


def test_the_prompt_is_not_logged(config, caplog):
    """The prompt is user content. It is already leaving the machine once; it
    does not also need to land in a log file someone else may read."""
    import logging

    def handler(request):
        return httpx.Response(200, content=_png_bytes(), headers={"content-type": "image/png"})

    secret = "internal codename bluebird"
    with caplog.at_level(logging.DEBUG, logger="mini_creative_toolkit"):
        generate_image_free(secret, 64, 64, client=_client(handler))
    assert secret not in caplog.text
    assert "Pollinations.ai" in caplog.text
