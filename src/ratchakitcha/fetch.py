"""Fetch the monthly spreadsheet and the homepage listing.

Requests stay small: the current month, the previous month number (the server
has ignored this parameter before; a duplicate body is discarded), and one
homepage GET. PDF bytes are downloaded only for items that are being summarized.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from datetime import date

from ratchakitcha.dates import bangkok_now
from ratchakitcha.dedupe import dedupe
from ratchakitcha.homepage import parse_homepage
from ratchakitcha.http_client import CloudflareChallenge, is_challenge, request
from ratchakitcha.models import Item
from ratchakitcha.xlsx_source import parse_xlsx

MONTHLY_URL = "https://apprkj.soc.go.th/report_documents_monthly.php"
HOMEPAGE_URL = "https://apprkj.soc.go.th/"

PostFunc = Callable[[str], tuple[int, bytes]]
GetFunc = Callable[[str], tuple[int, bytes]]


def _default_post(form: str) -> tuple[int, bytes]:
    status, body, _content_type = request(
        MONTHLY_URL,
        method="POST",
        data=form.encode("ascii"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://apprkj.soc.go.th",
            "Referer": "https://apprkj.soc.go.th/",
            "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
        },
    )
    return status, body


def _default_get(url: str) -> tuple[int, bytes]:
    status, body, _content_type = request(
        url,
        headers={"Accept": "text/html,application/xhtml+xml"},
    )
    return status, body


def _parse_month(status: int, body: bytes, label: str) -> list[Item]:
    if is_challenge(status, body):
        raise CloudflareChallenge(
            f"{label} returned a Cloudflare challenge (HTTP {status}). "
            "This digest does not bypass that challenge."
        )
    if status != 200:
        raise RuntimeError(f"{label} returned HTTP {status}")
    return parse_xlsx(body)


def fetch_items(
    *,
    today: date | None = None,
    post: PostFunc | None = None,
    get: GetFunc | None = None,
    pause_seconds: float = 1.0,
) -> list[Item]:
    post = post or _default_post
    get = get or _default_get
    current_day = today or bangkok_now().date()
    previous_month = 12 if current_day.month == 1 else current_day.month - 1

    status, current_body = post("month=0")
    items = _parse_month(status, current_body, "monthly xlsx (month=0)")
    current_hash = hashlib.sha256(current_body).hexdigest()

    if pause_seconds:
        time.sleep(pause_seconds)
    status, previous_body = post(f"month={previous_month}")
    previous_hash = hashlib.sha256(previous_body).hexdigest()
    if previous_hash != current_hash and not is_challenge(status, previous_body) and status == 200:
        try:
            items.extend(parse_xlsx(previous_body))
            print(f"[fetch] previous month={previous_month} added rows")
        except ValueError as error:
            print(f"[fetch] previous month response was not a usable workbook: {error}")
    elif is_challenge(status, previous_body):
        print("[fetch] previous-month request was challenged; keeping month=0")
    else:
        print("[fetch] previous-month workbook matches the current month; ignoring it")

    if pause_seconds:
        time.sleep(pause_seconds)
    try:
        home_status, home_body = get(HOMEPAGE_URL)
    except Exception as error:  # noqa: BLE001 - homepage is best-effort
        print(f"[fetch] homepage request failed: {error}")
        home_status, home_body = 0, b""

    if home_body and is_challenge(home_status, home_body):
        print(
            "[fetch] homepage is behind a Cloudflare challenge; "
            "continuing with the spreadsheet only"
        )
    elif home_status == 200 and home_body:
        html = home_body.decode("utf-8", errors="replace")
        homepage_items = parse_homepage(html)
        print(f"[fetch] homepage listing: {len(homepage_items)} dated items")
        items.extend(homepage_items)
    elif home_status:
        print(f"[fetch] homepage HTTP {home_status}; continuing with the spreadsheet only")

    merged = dedupe(items)
    print(f"[fetch] {len(merged)} unique documents")
    return merged
