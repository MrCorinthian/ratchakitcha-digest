"""Read and write data/items/YYYY-MM-DD.json without dropping late arrivals."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ratchakitcha.categories import SECTION_RANK
from ratchakitcha.models import Item, page_number

_ITEM_FIELDS = (
    "doc_id",
    "title",
    "date",
    "volume",
    "part",
    "section",
    "page",
    "book",
    "url",
    "category",
    "category_slug",
    "importance",
    "provinces",
    "source",
)


def sort_items(items: list[Item]) -> list[Item]:
    return sorted(
        items,
        key=lambda item: (
            -item.importance,
            SECTION_RANK.get(item.section, 9),
            page_number(item),
            item.doc_id,
        ),
    )


def _signature(items: list[Item]) -> str:
    payload = [{key: getattr(item, key) for key in _ITEM_FIELDS} for item in sort_items(items)]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def load_day(path: Path) -> list[Item]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Item.from_dict(row) for row in data.get("items", [])]


def load_all(items_dir: Path) -> dict[str, list[Item]]:
    days: dict[str, list[Item]] = {}
    if not items_dir.exists():
        return days
    for path in sorted(items_dir.glob("????-??-??.json")):
        items = load_day(path)
        if items:
            days[path.stem] = items
    return days


def known_doc_ids(items_dir: Path) -> set[str]:
    found: set[str] = set()
    for items in load_all(items_dir).values():
        found.update(item.doc_id for item in items)
    return found


def _write_day(path: Path, publication_date: str, items: list[Item], updated_at: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "publication_date": publication_date,
        "updated_at": updated_at,
        "items": [item.to_dict() for item in sort_items(items)],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_items(items_dir: Path, incoming: list[Item], now: datetime | None = None) -> set[str]:
    """Merge by document id. Returns ids that were not stored before this call.

    An id already stored under a publication date stays on that date. Items
    that disappear from a later export are kept. Files are rewritten only when
    the item records change, so a quiet cron run does not churn git history.
    """
    moment = now or datetime.now(timezone.utc)
    updated_at = moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    existing = load_all(items_dir)
    index: dict[str, str] = {}
    for publication_date, items in existing.items():
        for item in items:
            index[item.doc_id] = publication_date

    before = set(index)
    dirty: set[str] = set()
    buckets: dict[str, dict[str, Item]] = {
        publication_date: {item.doc_id: item for item in items}
        for publication_date, items in existing.items()
    }

    for item in incoming:
        if not item.date or not item.doc_id:
            continue
        publication_date = index.get(item.doc_id, item.date)
        bucket = buckets.setdefault(publication_date, {})
        bucket[item.doc_id] = item
        index[item.doc_id] = publication_date
        dirty.add(publication_date)

    for publication_date in dirty:
        items = list(buckets[publication_date].values())
        path = items_dir / f"{publication_date}.json"
        previous = existing.get(publication_date, [])
        if path.exists() and _signature(previous) == _signature(items):
            continue
        _write_day(path, publication_date, items, updated_at)

    return set(index) - before
