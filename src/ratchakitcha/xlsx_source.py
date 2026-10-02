"""Parse the monthly XLSX from POST /report_documents_monthly.php."""

from __future__ import annotations

import re
import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

from ratchakitcha.dates import excel_serial_to_iso, parse_human_date
from ratchakitcha.models import Item

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_DOC_ID = re.compile(r"/documents/(\d+)\.pdf", re.IGNORECASE)

_HEADER_ALIASES = {
    "วันที่": "date",
    "เรื่อง": "title",
    "เล่ม": "volume",
    "ตอน": "part",
    "ประเภท": "section",
    "หน้า": "page",
    "เล่มที่": "book",
    "URL": "url",
    "url": "url",
}


def official_pdf(doc_id: str) -> str:
    return f"https://ratchakitcha.soc.go.th/documents/{doc_id}.pdf"


def doc_id_from_url(url: str) -> str | None:
    match = _DOC_ID.search(url or "")
    return match.group(1) if match else None


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + (ord(char.upper()) - 64)
    return index


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for node in root.findall("m:si", _NS):
        values.append("".join(text.text or "" for text in node.findall(".//m:t", _NS)))
    return values


def _cell_text(cell: ET.Element, strings: list[str]) -> str:
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//m:t", _NS)).strip()
    value = cell.find("m:v", _NS)
    if value is None or value.text is None:
        return ""
    raw = value.text
    if kind == "s":
        return strings[int(raw)].strip()
    if re.fullmatch(r"-?\d+\.0+", raw):
        return str(int(float(raw)))
    return raw.strip()


def _rows(data: bytes) -> list[list[str]]:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        strings = _shared_strings(archive)
        sheet_name = "xl/worksheets/sheet1.xml"
        root = ET.fromstring(archive.read(sheet_name))
    parsed: list[list[str]] = []
    for row in root.findall(".//m:sheetData/m:row", _NS):
        cells: dict[int, str] = {}
        for cell in row.findall("m:c", _NS):
            ref = cell.get("r") or ""
            if not ref:
                continue
            cells[_column_index(ref)] = _cell_text(cell, strings)
        if not cells:
            parsed.append([])
            continue
        width = max(cells)
        parsed.append([cells.get(index, "") for index in range(1, width + 1)])
    return parsed


def _header_map(row: list[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for index, value in enumerate(row):
        key = _HEADER_ALIASES.get(value.strip())
        if key:
            mapping[key] = index
    if {"date", "title", "url"} <= mapping.keys():
        return mapping
    return None


def _field(row: list[str], mapping: dict[str, int], name: str) -> str:
    index = mapping.get(name)
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def _parse_date(raw: str) -> str | None:
    if not raw:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", raw):
        serial = excel_serial_to_iso(float(raw))
        if serial:
            return serial
    return parse_human_date(raw)


def parse_xlsx(data: bytes) -> list[Item]:
    if data[:2] != b"PK":
        raise ValueError("monthly report is not an xlsx file")
    rows = _rows(data)
    header_index = None
    mapping = None
    for index, row in enumerate(rows[:8]):
        mapping = _header_map(row)
        if mapping:
            header_index = index
            break
    if mapping is None or header_index is None:
        raise ValueError("monthly report is missing a header row")

    items: list[Item] = []
    for row in rows[header_index + 1 :]:
        if not any(cell.strip() for cell in row):
            continue
        url = _field(row, mapping, "url")
        doc_id = doc_id_from_url(url)
        title = _field(row, mapping, "title")
        if not doc_id or not title:
            continue
        parsed_date = _parse_date(_field(row, mapping, "date"))
        if not parsed_date:
            continue
        items.append(
            Item(
                doc_id=doc_id,
                title=title,
                date=parsed_date,
                volume=_field(row, mapping, "volume"),
                part=_field(row, mapping, "part"),
                section=_field(row, mapping, "section"),
                page=_field(row, mapping, "page"),
                book=_field(row, mapping, "book"),
                url=official_pdf(doc_id),
                source="xlsx",
            )
        )
    return items
