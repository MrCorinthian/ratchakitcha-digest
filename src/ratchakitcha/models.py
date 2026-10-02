"""Normalized gazette announcement."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields


@dataclass
class Item:
    doc_id: str
    title: str
    date: str
    volume: str = ""
    part: str = ""
    section: str = ""
    page: str = ""
    book: str = ""
    url: str = ""
    category: str = "อื่นๆ"
    category_slug: str = "other"
    importance: int = 0
    provinces: list[str] = field(default_factory=list)
    source: str = "xlsx"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Item:
        known = {item.name for item in fields(cls)}
        payload = {key: value for key, value in data.items() if key in known}
        payload["provinces"] = list(payload.get("provinces") or [])
        payload["importance"] = int(payload.get("importance") or 0)
        return cls(**payload)


def page_number(item: Item) -> int:
    digits = "".join(ch for ch in str(item.page) if ch.isdigit())
    return int(digits) if digits else 10**9
