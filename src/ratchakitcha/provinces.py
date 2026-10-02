"""Province tags from announcement titles.

Short names that also occur inside ordinary Thai words (แพร่, เลย, ตาก, …)
match only after จังหวัด or จ. Longer names match on their own. Longer spans win,
so กรุงเทพมหานคร is not also tagged as a shorter alias.
"""

from __future__ import annotations

import re

PROVINCES: tuple[str, ...] = (
    "กรุงเทพมหานคร",
    "กระบี่",
    "กาญจนบุรี",
    "กาฬสินธุ์",
    "กำแพงเพชร",
    "ขอนแก่น",
    "จันทบุรี",
    "ฉะเชิงเทรา",
    "ชลบุรี",
    "ชัยนาท",
    "ชัยภูมิ",
    "ชุมพร",
    "เชียงราย",
    "เชียงใหม่",
    "ตรัง",
    "ตราด",
    "ตาก",
    "นครนายก",
    "นครปฐม",
    "นครพนม",
    "นครราชสีมา",
    "นครศรีธรรมราช",
    "นครสวรรค์",
    "นนทบุรี",
    "นราธิวาส",
    "น่าน",
    "บึงกาฬ",
    "บุรีรัมย์",
    "ปทุมธานี",
    "ประจวบคีรีขันธ์",
    "ปราจีนบุรี",
    "ปัตตานี",
    "พระนครศรีอยุธยา",
    "พะเยา",
    "พังงา",
    "พัทลุง",
    "พิจิตร",
    "พิษณุโลก",
    "เพชรบุรี",
    "เพชรบูรณ์",
    "แพร่",
    "ภูเก็ต",
    "มหาสารคาม",
    "มุกดาหาร",
    "แม่ฮ่องสอน",
    "ยโสธร",
    "ยะลา",
    "ร้อยเอ็ด",
    "ระนอง",
    "ระยอง",
    "ราชบุรี",
    "ลพบุรี",
    "ลำปาง",
    "ลำพูน",
    "เลย",
    "ศรีสะเกษ",
    "สกลนคร",
    "สงขลา",
    "สตูล",
    "สมุทรปราการ",
    "สมุทรสงคราม",
    "สมุทรสาคร",
    "สระแก้ว",
    "สระบุรี",
    "สิงห์บุรี",
    "สุโขทัย",
    "สุพรรณบุรี",
    "สุราษฎร์ธานี",
    "สุรินทร์",
    "หนองคาย",
    "หนองบัวลำภู",
    "อ่างทอง",
    "อำนาจเจริญ",
    "อุดรธานี",
    "อุตรดิตถ์",
    "อุทัยธานี",
    "อุบลราชธานี",
)

# These strings are common inside unrelated words, so a bare match is unsafe.
PREFIX_ONLY = frozenset({"ตราด", "ตาก", "ตรัง", "น่าน", "แพร่", "ยะลา", "เลย", "สตูล", "กระบี่"})

ALIASES: tuple[tuple[str, str], ...] = (
    ("กรุงเทพฯ", "กรุงเทพมหานคร"),
    ("กทม.", "กรุงเทพมหานคร"),
)


def find_provinces(title: str) -> list[str]:
    spans: list[tuple[int, int, str]] = []
    for name in PROVINCES:
        prefix = re.compile(rf"(?:จังหวัด|จ\.)\s*{re.escape(name)}")
        for match in prefix.finditer(title):
            spans.append((match.start(), match.end(), name))
        if name not in PREFIX_ONLY:
            for match in re.finditer(re.escape(name), title):
                spans.append((match.start(), match.end(), name))
    for alias, name in ALIASES:
        for match in re.finditer(re.escape(alias), title):
            spans.append((match.start(), match.end(), name))

    spans.sort(key=lambda span: (-(span[1] - span[0]), span[0]))
    occupied: list[tuple[int, int]] = []
    found: list[tuple[int, str]] = []
    seen: set[str] = set()
    for start, end, name in spans:
        if any(not (end <= left or start >= right) for left, right in occupied):
            continue
        occupied.append((start, end))
        if name not in seen:
            seen.add(name)
            found.append((start, name))
    found.sort()
    return [name for _start, name in found]
