"""The only engine in this project that touches the network.

It is isolated here for two reasons. The obvious one is honesty: everything
that leaves the machine leaves through this file, so "what does this server
send anywhere?" has a one-file answer. The less obvious one is failure
containment - if Pollinations.ai disappears, starts requiring a key, or
starts returning HTML error pages with a 200 status, nothing outside this
module notices.

The response is *never* trusted. A 200 with ``Content-Type: text/html`` is
an error page, not an image; a 200 with a correct content type can still be
a truncated file; and a response with no length header can stream forever.
All three are handled before anything is written where a caller would find
it and treat it as an image.
"""

from __future__ import annotations

import io
import urllib.parse
from pathlib import Path

import httpx

from ..config import Config, get_config
from ..errors import NetworkError, ResourceLimitError
from ..log import get_logger

logger = get_logger(__name__)

BASE_URL = "https://image.pollinations.ai/prompt/"
SERVICE_NAME = "Pollinations.ai"

#: Content types we will accept as an image body. Anything else - notably
#: text/html, which is what a proxy or an error page returns - is refused.
ACCEPTED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def build_url(prompt: str) -> str:
    """The request URL. Separate from the request so tests can pin escaping."""
    return BASE_URL + urllib.parse.quote(prompt, safe="")


def fetch_image(
    prompt: str,
    width: int,
    height: int,
    seed: int | None = None,
    config: Config | None = None,
    client: httpx.Client | None = None,
) -> tuple[bytes, str]:
    """Fetch one generated image. Returns ``(bytes, detected_format)``.

    Logs the service and the operation, never the prompt: the prompt is user
    content, it is already leaving the machine once, and it does not also
    need to land in a log file that someone else may read.
    """
    config = config or get_config()
    params: dict[str, object] = {"width": width, "height": height, "nologo": "true"}
    if seed is not None:
        params["seed"] = seed

    logger.info(
        "generate_image_free: outbound request to %s (%dx%d) - this leaves the machine",
        SERVICE_NAME, width, height,
    )

    owns_client = client is None
    client = client or httpx.Client(timeout=config.http_timeout_seconds, follow_redirects=True)
    try:
        try:
            with client.stream("GET", build_url(prompt), params=params) as response:
                _check_status(response)
                _check_content_type(response)
                body = _read_bounded(response, config)
        except httpx.TimeoutException:
            raise NetworkError(
                f"{SERVICE_NAME} did not respond within {config.http_timeout_seconds:g}s. "
                f"It is a free public endpoint with no availability guarantee; retry, or "
                f"raise MCT_HTTP_TIMEOUT."
            ) from None
        except httpx.HTTPError as exc:
            raise NetworkError(
                f"Could not reach {SERVICE_NAME}: {type(exc).__name__}.", detail=repr(exc)
            ) from None
    finally:
        if owns_client:
            client.close()

    return body, _verify_decodes(body)


def _check_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    kind = "rejected the request" if response.status_code < 500 else "is failing"
    extra = ""
    if response.status_code in (401, 403):
        extra = (
            " A 401/403 from this endpoint would mean it has started requiring "
            "authentication, which it did not when this tool was written. Nothing "
            "else in this toolkit depends on it."
        )
    raise NetworkError(
        f"{SERVICE_NAME} {kind} (HTTP {response.status_code}).{extra}"
    )


def _check_content_type(response: httpx.Response) -> None:
    raw = response.headers.get("content-type", "")
    media_type = raw.split(";")[0].strip().lower()
    if media_type in ACCEPTED_TYPES:
        return
    raise NetworkError(
        f"{SERVICE_NAME} returned Content-Type {media_type or '(none)'!r}, not an image. "
        f"That usually means an error page was served with a success status. "
        f"Nothing was written."
    )


def _read_bounded(response: httpx.Response, config: Config) -> bytes:
    """Read the body, refusing to buffer more than the download limit.

    Checked while streaming rather than from Content-Length, which a server
    may omit, understate, or simply not send at all with chunked encoding.
    """
    limit = config.max_download_bytes
    buffer = io.BytesIO()
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > limit:
            response.close()
            raise ResourceLimitError(
                f"{SERVICE_NAME} response exceeded the {config.max_download_mb:g} MB "
                f"download limit and was aborted. Nothing was written. Raise "
                f"MCT_MAX_DOWNLOAD_MB if this is expected.",
                limit_name="MCT_MAX_DOWNLOAD_MB",
                limit_value=config.max_download_mb,
                actual=None,
            )
        buffer.write(chunk)
    if total == 0:
        raise NetworkError(f"{SERVICE_NAME} returned an empty body. Nothing was written.")
    return buffer.getvalue()


def _verify_decodes(body: bytes) -> str:
    """Confirm the bytes really are a decodable image before they are saved.

    A correct Content-Type is a claim; decoding is evidence. Without this, a
    truncated transfer would be written out as a ``.jpg`` that every later
    tool then fails on with a confusing error far from the real cause.
    """
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(body)) as img:
            img.verify()
            fmt = img.format
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise NetworkError(
            f"{SERVICE_NAME} returned {len(body)} bytes that are not a decodable image "
            f"(possibly a truncated transfer). Nothing was written.",
            detail=repr(exc),
        ) from None
    if not fmt:
        raise NetworkError(f"{SERVICE_NAME} returned an image of an unrecognised format.")
    return fmt


def save_image(body: bytes, destination: Path) -> None:
    destination.write_bytes(body)
