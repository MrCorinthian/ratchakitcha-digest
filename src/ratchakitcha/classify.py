"""Rule-based category, importance, and province tags. No network and no model."""

from __future__ import annotations

from dataclasses import replace

from ratchakitcha.categories import LABEL_BY_SLUG
from ratchakitcha.models import Item
from ratchakitcha.provinces import find_provinces

_BANKRUPTCY = ("พิทักษ์ทรัพย์", "ล้มละลาย", "คนไร้ความสามารถ", "คนเสมือนไร้ความสามารถ")
_DECORATION = (
    "เครื่องราชอิสริยาภรณ์",
    "เครื่องราชฯ",
    "ฐานันดร",
    "พระราชทานเครื่องราช",
    "สัญญาบัตร",
    "เลื่อนยศ",
    "พระราชทานยศ",
)
_LABOR = ("แรงงาน", "ประกันสังคม", "ค่าจ้าง", "เงินทดแทน", "ผู้ประกันตน")
_FINANCE = (
    "ภาษี",
    "สรรพากร",
    "สรรพสามิต",
    "ศุลกากร",
    "อากรแสตมป์",
    "ภาษีมูลค่าเพิ่ม",
    "ภาษีเงินได้",
)
_LAND = (
    "สำนักงานที่ดิน",
    "ผังเมือง",
    "เวนคืน",
    "จัดสรรที่ดิน",
    "โฉนดที่ดิน",
    "กรมที่ดิน",
    "อาคารชุด",
)
_LOCAL = ("เทศบัญญัติ", "ข้อบัญญัติ", "เทศบาล", "องค์การบริหารส่วน", "อบต.", "อบจ.")
_LAW_PREFIXES = (
    "พระราชบัญญัติ",
    "พระราชกำหนด",
    "พระราชกฤษฎีกา",
    "กฎกระทรวง",
    "รัฐธรรมนูญ",
    "ประมวลกฎหมาย",
    "ระเบียบ",
    "คำวินิจฉัย",
    "พระบรมราชโองการ",
)
# A citation of an act inside an ordinary announcement is not itself that act.
_LAW_CONTAINS = ("กฎกระทรวง", "ศาลรัฐธรรมนูญ")


def normalize_section(value: str) -> str:
    text = " ".join(str(value or "").replace("\u00a0", " ").split())
    text = text.replace("งพิเศษ", "ง พิเศษ")
    return text


def category_slug(title: str, section: str) -> str:
    text = title or ""
    section = normalize_section(section)
    if any(word in text for word in _BANKRUPTCY):
        return "bankruptcy"
    if section == "ข" or any(word in text for word in _DECORATION):
        return "decoration"
    if any(word in text for word in _LABOR):
        return "labor"
    if any(word in text for word in _FINANCE):
        return "finance"
    if any(word in text for word in _LAND):
        return "land"
    if any(word in text for word in _LOCAL):
        return "local"
    if text.startswith(_LAW_PREFIXES) or any(word in text for word in _LAW_CONTAINS):
        return "law"
    if "ประกาศกระทรวง" in text or text.startswith("ประกาศกรม"):
        return "ministry"
    return "other"


def importance_score(title: str, section: str) -> int:
    text = title or ""
    section = normalize_section(section)
    base = {"ก": 70, "ข": 58, "ค": 36, "ง": 24, "ง พิเศษ": 16}.get(section, 20)
    bonus = 0
    if text.startswith(("พระราชบัญญัติ", "พระราชกำหนด", "พระราชกฤษฎีกา", "รัฐธรรมนูญ")):
        bonus += 25
    elif "กฎกระทรวง" in text or text.startswith("ระเบียบ") or "ศาลรัฐธรรมนูญ" in text:
        bonus += 18
    elif "ประกาศกระทรวง" in text:
        bonus += 12
    if "แก้ไขข้อความคลาดเคลื่อน" in text:
        bonus -= 12
    if any(word in text for word in ("พิทักษ์ทรัพย์", "ล้มละลาย")):
        bonus -= 4
    return max(0, min(100, base + bonus))


def classify(item: Item) -> Item:
    section = normalize_section(item.section)
    slug = category_slug(item.title, section)
    return replace(
        item,
        section=section,
        category_slug=slug,
        category=LABEL_BY_SLUG[slug],
        importance=importance_score(item.title, section),
        provinces=find_provinces(item.title),
    )
