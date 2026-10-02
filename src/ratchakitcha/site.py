"""Build the Thai static site: home, day archive, categories, RSS, and Atom."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ratchakitcha.categories import CATEGORIES
from ratchakitcha.dates import bangkok_now, format_thai_date
from ratchakitcha.models import Item, page_number
from ratchakitcha.store import load_all, sort_items
from ratchakitcha.summaries import load_summary_map

DISCLAIMER = (
    "เว็บไซต์นี้เป็นสรุปรายวันอย่างไม่เป็นทางการของประกาศในราชกิจจานุเบกษา "
    "จัดทำขึ้นเพื่อช่วยให้ติดตามเรื่องใหม่ได้สะดวกขึ้น "
    "ไม่ใช่คำแนะนำทางกฎหมาย และไม่ใช่เว็บไซต์ของสำนักเลขาธิการคณะรัฐมนตรีหรือหน่วยงานของรัฐ "
    "ข้อความที่สมบูรณ์อยู่ที่ไฟล์ PDF บนเว็บไซต์ราชกิจจานุเบกษา "
    "วันที่ เลขเล่ม เลขตอน และเลขหน้าอ้างอิงจากข้อมูลเมตาดาตาของทางราชการ"
)

REPO_URL = "https://github.com/MrCorinthian/ratchakitcha-digest"
DEFAULT_SITE_URL = "https://mrcorinthian.github.io/ratchakitcha-digest"
_SECTION_CLASS = {
    "ก": "sec-ko",
    "ข": "sec-kho",
    "ค": "sec-q",
    "ง": "sec-ngo",
    "ง พิเศษ": "sec-extra",
}


def site_url() -> str:
    return os.environ.get("SITE_URL", DEFAULT_SITE_URL).rstrip("/")


def _rfc822(iso: str) -> str:
    year, month, day = (int(part) for part in iso.split("-"))
    try:
        tz = ZoneInfo("Asia/Bangkok")
    except ZoneInfoNotFoundError:
        tz = timezone(timedelta(hours=7))
    return format_datetime(datetime(year, month, day, 7, 30, tzinfo=tz))


def _prefix(depth: int) -> str:
    return "../" * depth


def _importance_label(score: int) -> str:
    if score >= 80:
        return "สำคัญมาก"
    if score >= 60:
        return "สำคัญ"
    return ""


def _meta_line(item: Item) -> str:
    bits = [format_thai_date(item.date)]
    location = " ".join(
        part
        for part in (
            f"เล่ม {item.volume}" if item.volume else "",
            f"ตอน {item.part}" if item.part else "",
            item.section,
            f"หน้า {item.page}" if item.page else "",
        )
        if part
    )
    if location:
        bits.append(location)
    if item.book:
        bits.append(f"เล่มที่ {item.book}")
    return " · ".join(bits)


def _render_item(item: Item, summary: dict[str, str] | None) -> str:
    section = item.section or "—"
    section_class = _SECTION_CLASS.get(item.section, "sec-other")
    flag = _importance_label(item.importance)
    flag_html = f'<span class="flag">{escape(flag)}</span>' if flag else ""
    provinces = ""
    if item.provinces:
        names = " ".join(escape(name) for name in item.provinces)
        provinces = f'<p class="provinces">จังหวัดที่เกี่ยวข้อง: {names}</p>'
    summary_html = ""
    if summary and summary.get("summary"):
        affected = ""
        if summary.get("affected"):
            affected = (
                f'<p class="affected"><span>ใครได้รับผลกระทบ</span> {escape(summary["affected"])}</p>'
            )
        summary_html = (
            f'<div class="summary"><p>{escape(summary["summary"])}</p>{affected}</div>'
        )
    pdf = (
        f'<p class="pdf"><a href="{escape(item.url, quote=True)}">ต้นฉบับ PDF</a></p>'
        if item.url
        else ""
    )
    return (
        f'<article class="item" id="d{escape(item.doc_id)}">'
        f'<p class="kicker"><span class="section {section_class}">{escape(section)}</span>'
        f'<a class="cat" href="{{{{CAT}}}}{escape(item.category_slug)}/">{escape(item.category)}</a>'
        f"{flag_html}</p>"
        f"<h3>{escape(item.title)}</h3>"
        f'<p class="meta">{escape(_meta_line(item))}</p>'
        f"{provinces}{summary_html}{pdf}"
        f"</article>"
    )


def _layout(title: str, body: str, depth: int, *, feed_href: str) -> str:
    prefix = _prefix(depth)
    description = "สรุปรายวันอย่างไม่เป็นทางการของราชกิจจานุเบกษา"
    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{escape(description)}">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'">
<title>{escape(title)}</title>
<link rel="stylesheet" href="{prefix}assets/style.css">
<link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="RSS" href="{escape(feed_href, quote=True)}">
</head>
<body>
<a class="skip" href="#content">ข้ามไปเนื้อหา</a>
<header class="masthead">
<p class="eyebrow">สรุปไม่เป็นทางการ</p>
<p class="brand"><a href="{prefix}">ราชกิจจานุเบกษา</a></p>
<p class="tagline">เรื่องใหม่จากราชกิจจานุเบกษา วันละสองรอบ</p>
<nav>
<a href="{prefix}">หน้าแรก</a>
<a href="{prefix}archive/">คลังรายวัน</a>
<a href="{prefix}category/">หมวด</a>
<a href="{prefix}feed.xml">RSS</a>
<a href="{prefix}atom.xml">Atom</a>
</nav>
</header>
<main id="content">
{body}
</main>
<footer>
<p>{escape(DISCLAIMER)}</p>
<p>แหล่งทางการ: <a href="https://ratchakitcha.soc.go.th/">ราชกิจจานุเบกษา</a>
· <a href="{REPO_URL}">โค้ดบน GitHub</a></p>
</footer>
</body>
</html>
"""


def _fix_category_links(html: str, depth: int) -> str:
    return html.replace("{{CAT}}", f"{_prefix(depth)}category/")


def _items_html(items: list[Item], summaries: dict[str, dict[str, str]], depth: int) -> str:
    chunks = [_render_item(item, summaries.get(item.doc_id)) for item in items]
    return _fix_category_links("".join(chunks), depth)


def _count_row(items: list[Item], depth: int) -> str:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.category_slug] = counts.get(item.category_slug, 0) + 1
    links = []
    prefix = _prefix(depth)
    for slug, label, _blurb in CATEGORIES:
        count = counts.get(slug, 0)
        if not count:
            continue
        links.append(
            f'<a href="{prefix}category/{slug}/">{escape(label)} <strong>{count}</strong></a>'
        )
    if not links:
        return ""
    return f'<p class="counts">{"".join(links)}</p>'


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _copy_assets(site_dir: Path, asset_dir: Path) -> None:
    target = site_dir / "assets"
    target.mkdir(parents=True, exist_ok=True)
    for path in asset_dir.iterdir():
        if path.is_file():
            (target / path.name).write_bytes(path.read_bytes())


def _rss(items: list[Item], *, feed_path: str, title: str, summaries: dict[str, dict[str, str]]) -> str:
    base = site_url()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        f"<title>{xml_escape(title)}</title>",
        f"<link>{xml_escape(base + '/')}</link>",
        f"<description>{xml_escape(DISCLAIMER)}</description>",
        "<language>th</language>",
        f'<atom:link href="{xml_escape(base + feed_path)}" rel="self" type="application/rss+xml"/>',
    ]
    for item in items:
        link = f"{base}/archive/{item.date}/#d{item.doc_id}"
        summary = summaries.get(item.doc_id, {})
        description = _meta_line(item)
        if summary.get("summary"):
            description = f"{description} — {summary['summary']}"
        lines.extend(
            [
                "<item>",
                f"<title>{xml_escape(item.title)}</title>",
                f"<link>{xml_escape(link)}</link>",
                f"<guid isPermaLink=\"false\">{xml_escape(item.url)}</guid>",
                f"<pubDate>{xml_escape(_rfc822(item.date))}</pubDate>",
                f"<category>{xml_escape(item.category)}</category>",
                f"<description>{xml_escape(description)}</description>",
                "</item>",
            ]
        )
    lines.extend(["</channel>", "</rss>", ""])
    return "\n".join(lines)


def _atom(items: list[Item], *, feed_path: str, title: str, summaries: dict[str, dict[str, str]]) -> str:
    base = site_url()
    updated = items[0].date if items else bangkok_now().date().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f"<title>{xml_escape(title)}</title>",
        f'<link href="{xml_escape(base + feed_path)}" rel="self"/>',
        f'<link href="{xml_escape(base + "/")}" rel="alternate"/>',
        f"<id>{xml_escape(base + feed_path)}</id>",
        f"<updated>{xml_escape(updated)}T00:00:00+07:00</updated>",
        f"<subtitle>{xml_escape(DISCLAIMER)}</subtitle>",
    ]
    for item in items:
        link = f"{base}/archive/{item.date}/#d{item.doc_id}"
        summary = summaries.get(item.doc_id, {})
        text = summary.get("summary") or _meta_line(item)
        lines.extend(
            [
                "<entry>",
                f"<title>{xml_escape(item.title)}</title>",
                f'<link href="{xml_escape(link)}"/>',
                f"<id>{xml_escape(link)}</id>",
                f"<updated>{xml_escape(item.date)}T00:00:00+07:00</updated>",
                f"<summary>{xml_escape(text)}</summary>",
                "</entry>",
            ]
        )
    lines.extend(["</feed>", ""])
    return "\n".join(lines)


def recent_items(days: dict[str, list[Item]], limit: int = 100) -> list[Item]:
    collected: list[Item] = []
    for items in days.values():
        collected.extend(items)
    collected.sort(key=lambda item: (item.date, item.importance, -page_number(item), item.doc_id), reverse=True)
    return collected[:limit]


def build_site(root: Path, site_dir: Path | None = None, notice: str = "") -> Path:
    items_dir = root / "data" / "items"
    summaries_dir = root / "data" / "summaries"
    output = site_dir or (root / "site")
    asset_dir = root / "assets"
    days = load_all(items_dir)
    summaries = load_summary_map(summaries_dir)
    today = bangkok_now().date().isoformat()
    if today in days:
        digest_date = today
        caught_up = True
    elif days:
        digest_date = max(days)
        caught_up = False
    else:
        digest_date = ""
        caught_up = False

    if output.exists():
        for path in sorted(output.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
        for path in sorted(output.rglob("*"), reverse=True):
            if path.is_dir():
                path.rmdir()
    output.mkdir(parents=True, exist_ok=True)
    _copy_assets(output, asset_dir)

    if digest_date:
        digest_items = sort_items(days[digest_date])
        note = ""
        if not caught_up:
            note = (
                f"<p class=\"lag\">วันนี้ ({escape(format_thai_date(today))}) "
                f"ยังไม่มีประกาศชุดใหม่ในข้อมูลที่ดึงมา "
                f"ด้านล่างเป็นประกาศล่าสุดวันที่ {escape(format_thai_date(digest_date))}</p>"
            )
        fetch_note = f'<p class="lag">{escape(notice)}</p>' if notice else ""
        body = (
            f"{fetch_note}"
            f"<h1>สรุปวันที่ {escape(format_thai_date(digest_date))}</h1>"
            f"{note}"
            f"<p class=\"lead\">{len(digest_items)} เรื่อง เรียงเรื่องสำคัญไว้ก่อน</p>"
            f"{_count_row(digest_items, 0)}"
            f'<p class="tools"><a href="archive/{digest_date}/">หน้าของวันนี้ในคลัง</a></p>'
            f"{_items_html(digest_items, summaries, 0)}"
        )
    else:
        fetch_note = f'<p class="lag">{escape(notice)}</p>' if notice else ""
        body = (
            f"{fetch_note}"
            "<h1>ยังไม่มีรายการ</h1>"
            "<p class=\"lead\">ระบบจะดึงประกาศวันละสองครั้ง เมื่อมีรายการใหม่ หน้านี้จะแสดงเรื่องสำคัญก่อน</p>"
        )
    _write(
        output / "index.html",
        _layout("ราชกิจจานุเบกษา สรุปรายวัน", body, 0, feed_href="feed.xml"),
    )

    archive_links = []
    for publication_date in sorted(days, reverse=True):
        count = len(days[publication_date])
        archive_links.append(
            f'<li><a href="{publication_date}/">{escape(format_thai_date(publication_date))}</a>'
            f"<span>{count} เรื่อง</span></li>"
        )
    archive_body = "<h1>คลังรายวัน</h1>" + (
        f"<ul class=\"daylist\">{''.join(archive_links)}</ul>" if archive_links else "<p>ยังไม่มีวันในคลัง</p>"
    )
    _write(
        output / "archive" / "index.html",
        _layout("คลังรายวัน", archive_body, 1, feed_href="../feed.xml"),
    )

    for publication_date, items in days.items():
        ordered = sort_items(items)
        body = (
            f"<h1>{escape(format_thai_date(publication_date))}</h1>"
            f"<p class=\"lead\">{len(ordered)} เรื่อง</p>"
            f"{_count_row(ordered, 2)}"
            f"{_items_html(ordered, summaries, 2)}"
        )
        _write(
            output / "archive" / publication_date / "index.html",
            _layout(
                f"ราชกิจจานุเบกษา {format_thai_date(publication_date)}",
                body,
                2,
                feed_href="../../feed.xml",
            ),
        )

    category_cards = []
    for slug, label, blurb in CATEGORIES:
        total = sum(1 for items in days.values() for item in items if item.category_slug == slug)
        category_cards.append(
            f'<li><a href="{slug}/"><strong>{escape(label)}</strong>'
            f"<span>{escape(blurb)}</span><em>{total} เรื่อง</em></a></li>"
        )
    _write(
        output / "category" / "index.html",
        _layout(
            "หมวดประกาศ",
            f"<h1>หมวดประกาศ</h1><ul class=\"cats\">{''.join(category_cards)}</ul>",
            1,
            feed_href="../feed.xml",
        ),
    )

    for slug, label, blurb in CATEGORIES:
        grouped: list[tuple[str, list[Item]]] = []
        for publication_date in sorted(days, reverse=True):
            chosen = [item for item in sort_items(days[publication_date]) if item.category_slug == slug]
            if chosen:
                grouped.append((publication_date, chosen))
        sections = [f"<h1>{escape(label)}</h1>", f"<p class=\"lead\">{escape(blurb)}</p>"]
        if not grouped:
            sections.append("<p>ยังไม่มีเรื่องในหมวดนี้</p>")
        for publication_date, chosen in grouped:
            sections.append(
                f'<h2><a href="../../archive/{publication_date}/">{escape(format_thai_date(publication_date))}</a></h2>'
            )
            sections.append(_items_html(chosen, summaries, 2))
        _write(
            output / "category" / slug / "index.html",
            _layout(label, "".join(sections), 2, feed_href="feed.xml"),
        )
        flat = [item for _date, chosen in grouped for item in chosen]
        ranked = sorted(
            flat,
            key=lambda item: (item.date, item.importance, item.doc_id),
            reverse=True,
        )[:100]
        _write(
            output / "category" / slug / "feed.xml",
            _rss(ranked, feed_path=f"/category/{slug}/feed.xml", title=f"ราชกิจจานุเบกษา · {label}", summaries=summaries),
        )
        _write(
            output / "category" / slug / "atom.xml",
            _atom(ranked, feed_path=f"/category/{slug}/atom.xml", title=f"ราชกิจจานุเบกษา · {label}", summaries=summaries),
        )

    latest = recent_items(days)
    _write(
        output / "feed.xml",
        _rss(latest, feed_path="/feed.xml", title="ราชกิจจานุเบกษา สรุปรายวัน", summaries=summaries),
    )
    _write(
        output / "atom.xml",
        _atom(latest, feed_path="/atom.xml", title="ราชกิจจานุเบกษา สรุปรายวัน", summaries=summaries),
    )
    _write(output / "robots.txt", "User-agent: *\nAllow: /\n")
    return output
