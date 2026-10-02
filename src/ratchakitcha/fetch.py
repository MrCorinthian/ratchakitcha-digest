"""Fetch the monthly spreadsheet and the homepage listing.

Requests stay small. The form that has succeeded is POST
``report_documents_monthly.php`` with ``month=0`` (current month). If that
response is a Cloudflare challenge, the same script is tried with the calendar
month, the previous month, a GET query string, and the www host. A challenge
is never solved. PDF bytes are downloaded only for items that are being
summarized.
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
WWW_MONTHLY_URL = "https://www.apprkj.soc.go.th/report_documents_monthly.php"
HOMEPAGE_URL = "https://apprkj.soc.go.th/"

Transport = Callable[[str, str, bytes | None, dict[str, str]], tuple[int, bytes]]
Sleep = Callable[[float], None]


class SpreadsheetUnavailable(CloudflareChallenge):
    """Every public spreadsheet request was challenged or unusable."""


def spreadsheet_attempts(today: date) -> list[tuple[str, str, str | None]]:
    """Public forms of the monthly report, in the order to try them.

    Each item is ``(method, url, form body or None)``. ``month=0`` is the
    current-month control. The calendar month (1–12) is sent as well because
    the server has sometimes ignored ``month`` and sometimes needs it.
    """
    current = str(today.month)
    previous = "12" if today.month == 1 else str(today.month - 1)
    apex = MONTHLY_URL
    return [
        ("POST", apex, "month=0"),
        ("POST", apex, f"month={current}"),
        ("POST", apex, f"month={previous}"),
        ("GET", f"{apex}?month=0", None),
        ("GET", f"{apex}?month={current}", None),
        ("POST", WWW_MONTHLY_URL, "month=0"),
        ("POST", WWW_MONTHLY_URL, f"month={current}"),
        ("POST", apex, "month=0"),
    ]


def _headers(method: str, url: str) -> dict[str, str]:
    if url.startswith("https://www.apprkj.soc.go.th"):
        origin = "https://www.apprkj.soc.go.th"
    else:
        origin = "https://apprkj.soc.go.th"
    headers = {
        "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
        "Referer": origin + "/",
    }
    if method == "POST":
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Origin"] = origin
    return headers


def _default_transport(
    method: str,
    url: str,
    data: bytes | None,
    headers: dict[str, str],
) -> tuple[int, bytes]:
    status, body, _content_type = request(url, method=method, data=data, headers=headers)
    return status, body


def _backoff(index: int) -> float:
    return float(min(30, 4 * (2**index)))


def _label(method: str, url: str, form: str | None) -> str:
    target = form or url
    return f"{method} {target}"


def _parse_workbook(status: int, body: bytes) -> list[Item] | None:
    if is_challenge(status, body) or status != 200 or not body.startswith(b"PK"):
        return None
    try:
        return parse_xlsx(body)
    except ValueError as error:
        print(f"[fetch] response was not a usable workbook: {error}")
        return None


def _request_form(
    transport: Transport,
    method: str,
    url: str,
    form: str | None,
) -> tuple[int, bytes]:
    data = form.encode("ascii") if form else None
    try:
        return transport(method, url, data, _headers(method, url))
    except Exception as error:  # noqa: BLE001 - try the next public form
        print(f"[fetch] {_label(method, url, form)} failed: {error}")
        return 0, b""


def _load_homepage(transport: Transport) -> list[Item]:
    try:
        status, body = transport(
            "GET",
            HOMEPAGE_URL,
            None,
            {"Accept": "text/html,application/xhtml+xml", "Referer": HOMEPAGE_URL},
        )
    except Exception as error:  # noqa: BLE001 - homepage is best-effort
        print(f"[fetch] homepage request failed: {error}")
        return []
    if is_challenge(status, body):
        print(
            "[fetch] homepage is behind a Cloudflare challenge; "
            "continuing without it"
        )
        return []
    if status != 200 or not body:
        print(f"[fetch] homepage HTTP {status}; continuing without it")
        return []
    html = body.decode("utf-8", errors="replace")
    items = parse_homepage(html)
    print(f"[fetch] homepage listing: {len(items)} dated items")
    return items


def fetch_items(
    *,
    today: date | None = None,
    transport: Transport | None = None,
    sleep: Sleep = time.sleep,
    pause_seconds: float = 1.0,
) -> list[Item]:
    transport = transport or _default_transport
    current_day = today or bangkok_now().date()
    attempts = spreadsheet_attempts(current_day)
    items: list[Item] = []
    seen_hashes: set[str] = set()
    got_workbook = False
    succeeded_form = ""
    previous_month = 12 if current_day.month == 1 else current_day.month - 1
    previous_form = f"month={previous_month}"

    for index, (method, url, form) in enumerate(attempts):
        label = _label(method, url, form)
        status, body = _request_form(transport, method, url, form)
        parsed = _parse_workbook(status, body)
        if parsed is None:
            if is_challenge(status, body):
                print(f"[fetch] {label} returned a Cloudflare challenge (HTTP {status})")
            else:
                print(f"[fetch] {label} was not a workbook (HTTP {status})")
            if index + 1 < len(attempts):
                delay = _backoff(index)
                print(f"[fetch] waiting {delay:.0f}s before the next spreadsheet request")
                sleep(delay)
            continue
        digest = hashlib.sha256(body).hexdigest()
        if digest in seen_hashes:
            print(f"[fetch] {label} matches a workbook already kept")
            got_workbook = True
            break
        seen_hashes.add(digest)
        items.extend(parsed)
        got_workbook = True
        succeeded_form = form or ""
        print(f"[fetch] {label} added {len(parsed)} rows")
        break

    if got_workbook and succeeded_form != previous_form:
        if pause_seconds:
            sleep(pause_seconds)
        status, body = _request_form(transport, "POST", MONTHLY_URL, previous_form)
        parsed = _parse_workbook(status, body)
        digest = hashlib.sha256(body).hexdigest() if body else ""
        if parsed and digest not in seen_hashes:
            items.extend(parsed)
            print(f"[fetch] previous month={previous_month} added rows")
        elif is_challenge(status, body):
            print("[fetch] previous-month request was challenged; keeping the workbook already fetched")
        elif parsed:
            print("[fetch] previous-month workbook matches one already kept")
        else:
            print(f"[fetch] previous-month request was not a workbook (HTTP {status})")

    if not got_workbook:
        homepage_items = _load_homepage(transport)
        if homepage_items:
            print("[fetch] spreadsheet was challenged; using the homepage listing only")
            return dedupe(homepage_items)
        raise SpreadsheetUnavailable(
            "monthly xlsx returned a Cloudflare challenge on every public form "
            "(POST month=0, the calendar month, GET, and www). "
            "This digest does not bypass that challenge."
        )

    if pause_seconds:
        sleep(pause_seconds)
    homepage_items = _load_homepage(transport)
    items.extend(homepage_items)
    merged = dedupe(items)
    print(f"[fetch] {len(merged)} unique documents")
    return merged
