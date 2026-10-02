from pathlib import Path

from ratchakitcha.dates import excel_serial_to_iso, parse_human_date
from ratchakitcha.dedupe import dedupe
from ratchakitcha.homepage import parse_homepage
from ratchakitcha.http_client import CloudflareChallenge, is_challenge
from ratchakitcha.models import Item
from ratchakitcha.store import load_day, merge_items
from ratchakitcha.xlsx_source import parse_xlsx

FIXTURE = Path(__file__).parent / "fixtures" / "sample_monthly_2026-10.xlsx"
HOMEPAGE = Path(__file__).parent / "fixtures" / "homepage_sample.html"


def test_parse_human_and_excel_dates():
    assert parse_human_date("01/10/2026") == "2026-10-01"
    assert parse_human_date("๑ ตุลาคม ๒๕๖๙") == "2026-10-01"
    assert parse_human_date("30 กันยายน 2569") == "2026-09-30"
    assert excel_serial_to_iso(45931) == "2025-10-01"
    assert excel_serial_to_iso(61) is None


def test_monthly_xlsx_fixture():
    items = parse_xlsx(FIXTURE.read_bytes())
    assert len(items) == 139
    assert len({item.doc_id for item in items}) == 139
    first = items[0]
    assert first.doc_id == "133319"
    assert first.date == "2026-10-01"
    assert first.section == "ก"
    assert first.volume == "143"
    assert first.part == "61"
    assert first.page == "1"
    assert first.url == "https://ratchakitcha.soc.go.th/documents/133319.pdf"
    assert first.title.startswith("ระเบียบคณะกรรมการตรวจเงินแผ่นดิน")
    assert all(item.date == "2026-10-01" for item in items)


def test_homepage_listing_and_month_rollover():
    items = {item.doc_id: item for item in parse_homepage(HOMEPAGE.read_text(encoding="utf-8"))}
    assert "999003" not in items
    previous = items["999001"]
    assert previous.date == "2026-09-30"
    assert previous.section == "ง พิเศษ"
    assert previous.part == "200"
    assert previous.page == "4"
    assert "เชียงใหม่" in previous.title
    late = items["999002"]
    assert late.date == "2026-10-02"
    assert late.section == "ง"
    assert late.url.endswith("/999002.pdf")
    duplicate = items["133319"]
    assert duplicate.date == "2025-10-01"
    assert duplicate.page == "99"


def test_dedupe_prefers_xlsx_metadata():
    spreadsheet = parse_xlsx(FIXTURE.read_bytes())
    homepage = parse_homepage(HOMEPAGE.read_text(encoding="utf-8"))
    merged = {item.doc_id: item for item in dedupe(spreadsheet + homepage)}
    assert len(merged) == 139 + 2
    kept = merged["133319"]
    assert kept.date == "2026-10-01"
    assert kept.page == "1"
    assert kept.title.startswith("ระเบียบคณะกรรมการตรวจเงินแผ่นดิน")
    assert merged["999001"].date == "2026-09-30"
    assert merged["999002"].date == "2026-10-02"


def test_store_keeps_late_items_and_does_not_drop_missing_rows(tmp_path):
    items_dir = tmp_path / "items"
    original = Item(
        doc_id="1",
        title="เรื่องเดิม",
        date="2026-09-30",
        url="https://ratchakitcha.soc.go.th/documents/1.pdf",
        source="xlsx",
    )
    late = Item(
        doc_id="2",
        title="เรื่องมาทีหลัง",
        date="2026-09-30",
        url="https://ratchakitcha.soc.go.th/documents/2.pdf",
        source="homepage",
    )
    assert merge_items(items_dir, [original]) == {"1"}
    assert merge_items(items_dir, [original, late]) == {"2"}
    stored = {item.doc_id: item for item in load_day(items_dir / "2026-09-30.json")}
    assert set(stored) == {"1", "2"}
    assert merge_items(items_dir, [late]) == set()
    stored = {item.doc_id: item for item in load_day(items_dir / "2026-09-30.json")}
    assert set(stored) == {"1", "2"}


def test_cloudflare_challenge_is_detected_and_not_parsed():
    body = b"<html><title>Just a moment...</title><script>challenge-platform</script></html>"
    assert is_challenge(403, body)
    assert not is_challenge(200, FIXTURE.read_bytes())
    try:
        raise CloudflareChallenge("stop")
    except CloudflareChallenge as error:
        assert "stop" in str(error)
