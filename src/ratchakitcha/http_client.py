"""Small HTTP helper. A Cloudflare challenge is reported and not bypassed."""

from __future__ import annotations

import urllib.error
import urllib.request

USER_AGENT = (
    "ratchakitcha-digest/0.1 "
    "(+https://github.com/MrCorinthian/ratchakitcha-digest; unofficial digest)"
)
MAX_BYTES = 20 * 1024 * 1024


class CloudflareChallenge(RuntimeError):
    """The origin returned a Cloudflare interstitial. Do not try to solve it."""


def is_challenge(status: int, body: bytes) -> bool:
    head = body[:8000].lower()
    if b"just a moment" in head or b"cf-challenge" in head or b"challenge-platform" in head:
        return True
    if status == 403 and b"cloudflare" in head:
        return True
    return False


def request(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 45,
) -> tuple[int, bytes, str]:
    merged = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Language": "th,en;q=0.8"}
    if headers:
        merged.update(headers)
    req = urllib.request.Request(url, data=data, headers=merged, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read(MAX_BYTES + 1)
            content_type = response.headers.get("Content-Type", "")
            status = response.status
    except urllib.error.HTTPError as error:
        body = error.read(MAX_BYTES + 1)
        content_type = error.headers.get("Content-Type", "") if error.headers else ""
        status = error.code
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"response from {url} is larger than {MAX_BYTES} bytes")
    return status, body, content_type
