import os
from pathlib import Path
from xml.etree import ElementTree as ET

from ratchakitcha.classify import classify
from ratchakitcha.site import DISCLAIMER, build_site
from ratchakitcha.store import merge_items
from ratchakitcha.summaries import upsert_summaries
from ratchakitcha.xlsx_source import parse_xlsx

FIXTURE = Path(__file__).parent / "fixtures" / "sample_monthly_2026-10.xlsx"
ROOT = Path(__file__).resolve().parents[1]


def _stage(tmp_path: Path) -> Path:
    items = [classify(item) for item in parse_xlsx(FIXTURE.read_bytes())]
    merge_items(tmp_path / "data" / "items", items)
    upsert_summaries(
        tmp_path / "data" / "summaries",
        {
            "2026-10-01": [
                {
                    "doc_id": "133319",
                    "summary": "แก้ไขระเบียบกำกับการตรวจเงินแผ่นดิน",
                    "affected": "คณะกรรมการตรวจเงินแผ่นดินและสำนักงานการตรวจเงินแผ่นดิน",
                    "generated_by": "cursor-automation",
                }
            ]
        },
    )
    assets = tmp_path / "assets"
    assets.mkdir()
    for path in (ROOT / "assets").iterdir():
        if path.is_file():
            (assets / path.name).write_bytes(path.read_bytes())
    return tmp_path


def test_site_pages_feeds_and_links(tmp_path, monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://example.test/ratchakitcha-digest")
    root = _stage(tmp_path)
    site = build_site(root, site_dir=tmp_path / "site")
    index = (site / "index.html").read_text(encoding="utf-8")
    assert "ราชกิจจานุเบกษา" in index
    assert DISCLAIMER in index
    assert "ระเบียบคณะกรรมการตรวจเงินแผ่นดิน" in index
    assert "แก้ไขระเบียบกำกับการตรวจเงินแผ่นดิน" in index
    assert "ใครได้รับผลกระทบ" in index
    assert "<script" not in index.lower()
    assert "Content-Security-Policy" in index
    assert 'href="assets/style.css"' in index

    day = (site / "archive" / "2026-10-01" / "index.html").read_text(encoding="utf-8")
    assert 'href="../../assets/style.css"' in day
    assert 'id="d133319"' in day
    assert "ต้นฉบับ PDF" in day

    law = (site / "category" / "law" / "index.html").read_text(encoding="utf-8")
    assert "กฎหมาย" in law
    assert (site / "category" / "bankruptcy" / "index.html").exists()
    assert (site / "category" / "law" / "feed.xml").exists()
    assert (site / "category" / "law" / "atom.xml").exists()

    feed = ET.fromstring((site / "feed.xml").read_text(encoding="utf-8"))
    titles = [node.text for node in feed.findall("./channel/item/title")]
    assert titles
    assert any("ตรวจเงินแผ่นดิน" in (title or "") for title in titles)
    link = feed.find("./channel/item/link").text
    assert link.startswith("https://example.test/ratchakitcha-digest/archive/")
    atom = ET.fromstring((site / "atom.xml").read_text(encoding="utf-8"))
    assert atom.tag.endswith("feed")

    for html_path in site.rglob("*.html"):
        text = html_path.read_text(encoding="utf-8")
        depth = len(html_path.relative_to(site).parts) - 1
        assert "<script" not in text.lower()
        for raw in _hrefs(text):
            if raw.startswith(("http://", "https://", "mailto:")):
                continue
            target = raw.split("#", 1)[0]
            if not target:
                continue
            resolved = (html_path.parent / target).resolve()
            assert resolved.exists(), f"{html_path} -> {raw}"
        assert depth >= 0


def _hrefs(html: str) -> list[str]:
    import re

    return re.findall(r'href="([^"]+)"', html)


def test_workflow_schedule_is_twice_daily():
    text = (ROOT / ".github" / "workflows" / "digest.yml").read_text(encoding="utf-8")
    assert "30 0 * * *" in text
    assert "30 12 * * *" in text
    assert "workflow_dispatch" in text
    assert "TELEGRAM_BOT_TOKEN" in text
    assert "BUTTONDOWN_API_KEY" in text
    assert "GEMINI_API_KEY" in text
    assert os.environ.get("TELEGRAM_BOT_TOKEN", "") == ""
