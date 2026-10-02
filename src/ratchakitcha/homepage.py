"""Parse the apprkj homepage listing.

The live theme uses post-thumbnail cards, data-document-title, and
data-document-link (see the public theme scripts). Each PDF link is read from
its own window so a missing title on one card does not steal the next card's
text. Dates and numbers are parsed here only as a fallback; the monthly XLSX
wins when both sources have the same document.
"""

from __future__ import annotations

import re
from html import unescape

from ratchakitcha.dates import normalize_digits, parse_human_date
from ratchakitcha.models import Item
from ratchakitcha.xlsx_source import doc_id_from_url, official_pdf

_PDF = re.compile(r"/documents/(\d+)\.pdf", re.IGNORECASE)
_ATTR = re.compile(
    r"""data-document-(title|link)\s*=\s*(?:"([^"]*)"|'([^']*)')""",
    re.IGNORECASE,
)
_DATE_BLOCK = re.compile(
    r"""class="[^"]*date-news\d*[^"]*"[^>]*>(.*?)</""",
    re.IGNORECASE | re.DOTALL,
)
_TITLE_BLOCK = re.compile(
    r"""class="[^"]*(?:title-news|post-title)[^"]*"[^>]*>(.*?)</""",
    re.IGNORECASE | re.DOTALL,
)
_META = re.compile(
    r"เล่ม\s*([0-9]+)\s*ตอน(พิเศษ|ที่)?\s*([0-9]+)\s*(ก|ข|ค|ง)(\s*พิเศษ)?(?:\s*หน้า\s*([0-9]+))?"
)
_TAG = re.compile(r"<[^>]+>")
_SKIP_LINK_TEXT = frozenset(
    {"ดูรายละเอียด", "ดาวน์โหลด", "download", "คัดลอก", "copy", "ดูเพิ่ม", "รายละเอียด"}
)


def _strip(html: str) -> str:
    text = _TAG.sub(" ", html)
    return " ".join(unescape(text).split())


def _attr_map(window: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for match in _ATTR.finditer(window):
        found[match.group(1).lower()] = unescape(match.group(2) or match.group(3) or "").strip()
    return found


def _anchor_texts(window: str) -> list[str]:
    texts: list[str] = []
    for match in re.finditer(r"<a\b[^>]*>(.*?)</a>", window, re.IGNORECASE | re.DOTALL):
        text = _strip(match.group(1))
        if text and text.casefold() not in _SKIP_LINK_TEXT and len(text) >= 8:
            texts.append(text)
    return texts


def _section_from_match(match: re.Match[str]) -> tuple[str, str, str, str]:
    volume, special_word, part, letter, extra_special, page = match.groups()
    section = letter
    if letter == "ง" and (special_word == "พิเศษ" or extra_special):
        section = "ง พิเศษ"
    return volume, part, section, page or ""


def parse_window(window: str) -> Item | None:
    attrs = _attr_map(window)
    link = attrs.get("link", "")
    doc_id = doc_id_from_url(link) or doc_id_from_url(window)
    if not doc_id:
        pdfs = _PDF.findall(window)
        doc_id = pdfs[0] if pdfs else None
    if not doc_id:
        return None

    plain = normalize_digits(_strip(window))
    date_html = _DATE_BLOCK.search(window)
    date_text = normalize_digits(_strip(date_html.group(1))) if date_html else plain
    parsed_date = parse_human_date(date_text) or parse_human_date(plain)
    if not parsed_date:
        return None

    title = attrs.get("title", "")
    if len(title) < 8:
        block = _TITLE_BLOCK.search(window)
        title = _strip(block.group(1)) if block else ""
    if len(title) < 8:
        anchors = _anchor_texts(window)
        title = max(anchors, key=len) if anchors else ""
    if len(title) < 8:
        leftover = _META.sub(" ", plain)
        leftover = re.sub(r"\d{1,2}\s+\S+\s+\d{4}", " ", leftover)
        for noise in ("ดูรายละเอียด", "ดาวน์โหลด", "ราชกิจจานุเบกษา"):
            leftover = leftover.replace(noise, " ")
        leftover = " ".join(leftover.split())
        title = leftover if len(leftover) >= 8 else ""

    volume = part = section = page = ""
    meta = _META.search(plain)
    if meta:
        volume, part, section, page = _section_from_match(meta)

    return Item(
        doc_id=doc_id,
        title=title,
        date=parsed_date,
        volume=volume,
        part=part,
        section=section,
        page=page,
        url=official_pdf(doc_id),
        source="homepage",
    )


def parse_homepage(html: str) -> list[Item]:
    html = html.lstrip("\ufeff")
    positions = [match.start() for match in _PDF.finditer(html)]
    if not positions:
        return []
    items: list[Item] = []
    seen: dict[str, Item] = {}
    for index, pos in enumerate(positions):
        previous_end = positions[index - 1] + 1 if index else 0
        nxt = positions[index + 1] if index + 1 < len(positions) else len(html)
        entry = html.rfind("post-thumbnail-entry", previous_end, pos)
        # Bare links start at the URL so a date that trails the previous card
        # is not read as this card's date. Theme cards look back to the entry.
        start = entry if entry != -1 else pos
        end = nxt if index + 1 < len(positions) else min(len(html), pos + 700)
        window = html[start:end]
        item = parse_window(window)
        if item is None:
            continue
        current = seen.get(item.doc_id)
        if current is None:
            seen[item.doc_id] = item
            items.append(item)
            continue
        if len(item.title) > len(current.title):
            current.title = item.title
        if not current.section and item.section:
            current.section = item.section
            current.volume = item.volume
            current.part = item.part
            current.page = item.page
    return items
