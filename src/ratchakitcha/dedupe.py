"""Dedupe announcements by PDF document id.

XLSX metadata wins for the title, date, and numbers. A homepage row fills
fields the spreadsheet left blank and can add a document the spreadsheet
does not have yet (late items and the previous month).
"""

from __future__ import annotations

from dataclasses import replace

from ratchakitcha.models import Item

_FILL = ("title", "date", "volume", "part", "section", "page", "book", "url")


def _blank(value: str) -> bool:
    return not str(value or "").strip()


def prefer(left: Item, right: Item) -> Item:
    if left.source == "xlsx" and right.source != "xlsx":
        base, extra = left, right
    elif right.source == "xlsx" and left.source != "xlsx":
        base, extra = right, left
    elif len(left.title) >= len(right.title):
        base, extra = left, right
    else:
        base, extra = right, left

    data = base.to_dict()
    filled = False
    for key in _FILL:
        if _blank(data.get(key, "")) and not _blank(getattr(extra, key)):
            data[key] = getattr(extra, key)
            filled = True
    source = base.source
    if filled and extra.source and extra.source != base.source:
        source = "merged"
    elif base.source == "xlsx":
        source = "xlsx"
    return replace(Item.from_dict(data), source=source)


def dedupe(items: list[Item]) -> list[Item]:
    ordered: list[Item] = []
    by_id: dict[str, Item] = {}
    for item in items:
        current = by_id.get(item.doc_id)
        if current is None:
            by_id[item.doc_id] = item
            ordered.append(item)
            continue
        merged = prefer(current, item)
        by_id[item.doc_id] = merged
        index = next(pos for pos, existing in enumerate(ordered) if existing.doc_id == item.doc_id)
        ordered[index] = merged
    return ordered
