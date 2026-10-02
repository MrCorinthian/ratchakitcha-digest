from datetime import date
from pathlib import Path

import pytest

from ratchakitcha.fetch import HOMEPAGE_URL, MONTHLY_URL, SpreadsheetUnavailable, fetch_items, spreadsheet_attempts
from ratchakitcha.models import Item
from ratchakitcha.pipeline import SAVED_COPY_NOTICE, run
from ratchakitcha.raw_xlsx import select_items

FIXTURE = Path(__file__).parent / "fixtures" / "sample_monthly_2026-10.xlsx"
HOME = Path(__file__).parent / "fixtures" / "homepage_sample.html"
ROOT = Path(__file__).resolve().parents[1]
CHALLENGE = b"<html><title>Just a moment...</title>challenge-platform</html>"
TODAY = date(2026, 10, 2)


def test_attempt_order_includes_calendar_month_get_and_www():
    attempts = spreadsheet_attempts(TODAY)
    assert attempts[0] == ("POST", MONTHLY_URL, "month=0")
    assert ("POST", MONTHLY_URL, "month=10") in attempts
    assert ("POST", MONTHLY_URL, "month=9") in attempts
    assert ("GET", f"{MONTHLY_URL}?month=10", None) in attempts
    assert any(url.startswith("https://www.apprkj.soc.go.th/") for _method, url, _form in attempts)
    assert attempts[-1] == ("POST", MONTHLY_URL, "month=0")


def test_calendar_month_is_used_when_month_zero_is_challenged():
    workbook = FIXTURE.read_bytes()
    calls: list[tuple[str, str, bytes | None]] = []
    delays: list[float] = []

    def transport(method, url, data, headers):
        calls.append((method, url, data))
        if data == b"month=10":
            assert headers["Origin"] == "https://apprkj.soc.go.th"
            assert headers["Content-Type"] == "application/x-www-form-urlencoded"
            assert headers["Referer"] == "https://apprkj.soc.go.th/"
            return 200, workbook
        return 403, CHALLENGE

    items = fetch_items(today=TODAY, transport=transport, sleep=delays.append, pause_seconds=0)
    assert any(item.doc_id == "133319" for item in items)
    assert calls[0] == ("POST", MONTHLY_URL, b"month=0")
    assert calls[1] == ("POST", MONTHLY_URL, b"month=10")
    assert ("POST", MONTHLY_URL, b"month=9") in calls
    assert delays == [4.0]
    assert not any(method == "GET" and url.startswith(MONTHLY_URL) for method, url, _data in calls)


def test_month_zero_success_does_not_try_later_forms():
    workbook = FIXTURE.read_bytes()
    bodies: list[bytes | None] = []

    def transport(method, url, data, headers):
        bodies.append(data)
        if data in (b"month=0", b"month=9"):
            return 200, workbook
        return 403, CHALLENGE

    items = fetch_items(today=TODAY, transport=transport, sleep=lambda _seconds: None, pause_seconds=0)
    assert len(items) == 139
    assert b"month=10" not in bodies
    assert bodies[0] == b"month=0"
    assert b"month=9" in bodies


def test_challenged_spreadsheet_can_fall_back_to_homepage():
    html = HOME.read_bytes()

    def transport(method, url, data, headers):
        if url == HOMEPAGE_URL:
            return 200, html
        return 403, CHALLENGE

    items = fetch_items(today=TODAY, transport=transport, sleep=lambda _seconds: None, pause_seconds=0)
    ids = {item.doc_id for item in items}
    assert "999001" in ids
    assert "999003" not in ids


def test_every_public_form_challenged_raises_without_a_bypass():
    calls: list[tuple[str, str, bytes | None]] = []

    def transport(method, url, data, headers):
        calls.append((method, url, data))
        return 403, CHALLENGE

    with pytest.raises(SpreadsheetUnavailable, match="does not bypass"):
        fetch_items(today=TODAY, transport=transport, sleep=lambda _seconds: None, pause_seconds=0)
    posted = [data.decode() for _method, _url, data in calls if data]
    assert posted.count("month=0") >= 2
    assert "month=10" in posted
    assert any(method == "GET" and "month=10" in url for method, url, _data in calls)
    assert any("www.apprkj.soc.go.th" in url for _method, url, _data in calls)
    assert any(url == HOMEPAGE_URL for _method, url, _data in calls)


def test_blocked_fetch_keeps_saved_items_and_builds(tmp_path, monkeypatch):
    root = tmp_path
    items = root / "data" / "items"
    items.mkdir(parents=True)
    saved = (ROOT / "data" / "items" / "2026-10-01.json").read_text(encoding="utf-8")
    (items / "2026-10-01.json").write_text(saved, encoding="utf-8")
    assets = root / "assets"
    assets.mkdir()
    for path in (ROOT / "assets").iterdir():
        if path.is_file():
            (assets / path.name).write_bytes(path.read_bytes())

    def blocked(**_kwargs):
        raise SpreadsheetUnavailable("monthly xlsx challenged")

    notified = {"called": False}

    def deliver(**_kwargs):
        notified["called"] = True
        raise AssertionError("notifications must wait for a successful fetch")

    monkeypatch.setattr("ratchakitcha.pipeline.fetch_items", blocked)
    monkeypatch.setattr("ratchakitcha.pipeline.deliver", deliver)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert run(root) == set()
    assert (items / "2026-10-01.json").read_text(encoding="utf-8") == saved
    index = (root / "site" / "index.html").read_text(encoding="utf-8")
    assert SAVED_COPY_NOTICE in index
    assert "133319" in index
    assert notified["called"] is False


def _item(doc_id: str, publication_date: str, source: str = "xlsx") -> Item:
    return Item(
        doc_id=doc_id,
        title=f"เรื่อง {doc_id}",
        date=publication_date,
        url=f"https://ratchakitcha.soc.go.th/documents/{doc_id}.pdf",
        source=source,
    )


def test_newer_committed_workbook_wins_and_homepage_rows_stay():
    live = [_item("1", "2026-10-01"), _item("9", "2026-10-02", source="homepage")]
    raw = [_item("1", "2026-10-01"), _item("2", "2026-10-02")]
    chosen = {item.doc_id: item for item in select_items(live, raw)}
    assert set(chosen) == {"1", "2", "9"}
    assert chosen["2"].source == "xlsx"
    assert chosen["9"].source == "homepage"


def test_newer_live_workbook_is_not_replaced_by_an_older_file():
    live = [_item("3", "2026-10-02")]
    raw = [_item("1", "2026-10-01"), _item("2", "2026-10-01")]
    chosen = select_items(live, raw)
    assert {item.doc_id for item in chosen} == {"3"}


def test_blocked_fetch_ingests_committed_xlsx(tmp_path, monkeypatch):
    root = tmp_path
    raw = root / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "monthly-latest.xlsx").write_bytes(FIXTURE.read_bytes())
    (raw / "monthly-2026-10.xlsx").write_bytes(FIXTURE.read_bytes())
    assets = root / "assets"
    assets.mkdir()
    for path in (ROOT / "assets").iterdir():
        if path.is_file():
            (assets / path.name).write_bytes(path.read_bytes())

    def blocked(**_kwargs):
        raise SpreadsheetUnavailable("monthly xlsx challenged")

    monkeypatch.setattr("ratchakitcha.pipeline.fetch_items", blocked)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("BUTTONDOWN_API_KEY", raising=False)

    new_ids = run(root)
    assert "133319" in new_ids
    index = (root / "site" / "index.html").read_text(encoding="utf-8")
    assert SAVED_COPY_NOTICE not in index
    assert "ระเบียบคณะกรรมการตรวจเงินแผ่นดิน" in index
