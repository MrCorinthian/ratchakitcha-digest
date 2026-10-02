"""Read the spreadsheet committed from a machine that can reach apprkj."""

from __future__ import annotations

from pathlib import Path

from ratchakitcha.dedupe import dedupe
from ratchakitcha.models import Item
from ratchakitcha.xlsx_source import parse_xlsx

LATEST_NAME = "monthly-latest.xlsx"


def _is_xlsx(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(2) == b"PK"
    except OSError:
        return False


def committed_workbook_path(root: Path) -> Path | None:
    """Prefer monthly-latest.xlsx, then the newest monthly-YYYY-MM.xlsx."""
    raw_dir = root / "data" / "raw"
    latest = raw_dir / LATEST_NAME
    if _is_xlsx(latest):
        return latest
    dated = sorted(path for path in raw_dir.glob("monthly-????-??.xlsx") if _is_xlsx(path))
    return dated[-1] if dated else None


def load_committed_items(root: Path) -> list[Item]:
    path = committed_workbook_path(root)
    if path is None:
        print("[fetch] no committed workbook in data/raw")
        return []
    try:
        items = parse_xlsx(path.read_bytes())
    except ValueError as error:
        print(f"[fetch] {path.name} is not a usable workbook: {error}")
        return []
    print(f"[fetch] committed workbook {path.relative_to(root)} has {len(items)} rows")
    return items


def _freshness(items: list[Item]) -> tuple[str, int]:
    dates = [item.date for item in items if item.date]
    return (max(dates) if dates else "", len(items))


def select_items(live: list[Item], raw: list[Item]) -> list[Item]:
    """Pick the newer spreadsheet and keep homepage-only rows from the live fetch.

    Freshness is the latest publication date, then the number of rows. A tie
    merges both workbooks. Homepage rows are not a spreadsheet, so a single
    newer listing cannot replace a fuller committed workbook.
    """
    live_sheet = [item for item in live if item.source == "xlsx"]
    extras = [item for item in live if item.source != "xlsx"]
    chosen = _prefer_workbook(live_sheet, raw)
    return dedupe(chosen + extras)


def _prefer_workbook(live: list[Item], raw: list[Item]) -> list[Item]:
    if not raw:
        print(f"[fetch] using live workbook ({len(live)} rows)")
        return live
    if not live:
        print(f"[fetch] using committed workbook ({len(raw)} rows)")
        return raw
    live_key = _freshness(live)
    raw_key = _freshness(raw)
    if raw_key > live_key:
        print(
            f"[fetch] committed workbook is newer ({raw_key[0]}, {raw_key[1]} rows); "
            "not using the older live workbook"
        )
        return raw
    if live_key > raw_key:
        print(f"[fetch] live workbook is newer ({live_key[0]}, {live_key[1]} rows)")
        return live
    print("[fetch] live and committed workbooks are the same date and size; merging both")
    return dedupe(live + raw)
