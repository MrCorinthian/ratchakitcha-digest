"""Date helpers. Gazette metadata uses CE dates; Thai prose uses พ.ศ."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

THAI_MONTHS: tuple[tuple[str, int], ...] = (
    ("พฤศจิกายน", 11),
    ("กุมภาพันธ์", 2),
    ("พฤษภาคม", 5),
    ("สิงหาคม", 8),
    ("มกราคม", 1),
    ("กันยายน", 9),
    ("ธันวาคม", 12),
    ("ตุลาคม", 10),
    ("เมษายน", 4),
    ("มิถุนายน", 6),
    ("กรกฎาคม", 7),
    ("มีนาคม", 3),
    ("พ.ย.", 11),
    ("ก.พ.", 2),
    ("พ.ค.", 5),
    ("ส.ค.", 8),
    ("ม.ค.", 1),
    ("ก.ย.", 9),
    ("ธ.ค.", 12),
    ("ต.ค.", 10),
    ("เม.ย.", 4),
    ("มิ.ย.", 6),
    ("ก.ค.", 7),
    ("มี.ค.", 3),
)

THAI_MONTH_NAME = (
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
)

_MONTH_PATTERN = "|".join(re.escape(name) for name, _ in THAI_MONTHS)
_MONTH_INDEX = {name: number for name, number in THAI_MONTHS}


def bangkok_now() -> datetime:
    try:
        tz = ZoneInfo("Asia/Bangkok")
    except ZoneInfoNotFoundError:
        tz = timezone(timedelta(hours=7))
    return datetime.now(tz)


def normalize_digits(text: str) -> str:
    return text.translate(THAI_DIGITS).replace("\u00a0", " ").replace("\u200b", "")


def to_ce_year(year: int) -> int:
    if year >= 2400:
        return year - 543
    return year


def iso_date(year: int, month: int, day: int) -> str | None:
    year = to_ce_year(year)
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_human_date(text: str) -> str | None:
    """Parse dd/mm/yyyy or '1 ตุลาคม 2569' from a short string. Years >= 2400 are พ.ศ."""
    cleaned = " ".join(normalize_digits(text).split())
    numeric = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", cleaned)
    if numeric:
        day, month, year = (int(part) for part in numeric.groups())
        return iso_date(year, month, day)
    named = re.search(rf"(\d{{1,2}})\s+({_MONTH_PATTERN})\s+(\d{{4}})", cleaned)
    if named:
        day = int(named.group(1))
        month = _MONTH_INDEX[named.group(2)]
        year = int(named.group(3))
        return iso_date(year, month, day)
    return None


def excel_serial_to_iso(serial: float) -> str | None:
    """Excel 1900 date system. Rejects values that are ordinary small integers."""
    if serial < 20000 or serial > 80000:
        return None
    parsed = date(1899, 12, 30) + timedelta(days=int(serial))
    return parsed.isoformat()


def format_thai_date(iso: str) -> str:
    year, month, day = (int(part) for part in iso.split("-"))
    return f"{day} {THAI_MONTH_NAME[month - 1]} {year + 543}"
