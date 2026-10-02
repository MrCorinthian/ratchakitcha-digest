"""Merge data/summaries/YYYY-MM-DD.json into the site.

Files already on disk win. Gemini and the Cursor automation only fill document
ids that do not have a summary yet, so a later run does not overwrite a
reviewed summary.
"""

from __future__ import annotations

import json
from pathlib import Path

from ratchakitcha.models import Item


def clean_text(value: str, limit: int = 1200) -> str:
    text = " ".join(str(value or "").replace("\r", "\n").split())
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def load_summary_map(summaries_dir: Path) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    if not summaries_dir.exists():
        return found
    for path in sorted(summaries_dir.glob("????-??-??.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("items", []):
            doc_id = str(row.get("doc_id") or "").strip()
            summary = clean_text(row.get("summary", ""))
            if not doc_id or not summary:
                continue
            found[doc_id] = {
                "doc_id": doc_id,
                "summary": summary,
                "affected": clean_text(row.get("affected", ""), limit=400),
                "generated_by": str(row.get("generated_by") or ""),
            }
    return found


def upsert_summaries(
    summaries_dir: Path,
    rows_by_date: dict[str, list[dict[str, str]]],
) -> int:
    """Add summaries for doc ids that are not already stored. Returns the count added."""
    summaries_dir.mkdir(parents=True, exist_ok=True)
    added = 0
    for publication_date, rows in rows_by_date.items():
        path = summaries_dir / f"{publication_date}.json"
        if path.exists():
            current = json.loads(path.read_text(encoding="utf-8"))
        else:
            current = {"publication_date": publication_date, "items": []}
        existing = {str(row.get("doc_id")): row for row in current.get("items", [])}
        changed = False
        for row in rows:
            doc_id = str(row.get("doc_id") or "").strip()
            summary = clean_text(row.get("summary", ""))
            if not doc_id or not summary or doc_id in existing:
                continue
            existing[doc_id] = {
                "doc_id": doc_id,
                "summary": summary,
                "affected": clean_text(row.get("affected", ""), limit=400),
                "generated_by": str(row.get("generated_by") or ""),
            }
            added += 1
            changed = True
        if not changed:
            continue
        ordered = sorted(existing.values(), key=lambda row: row["doc_id"])
        payload = {"publication_date": publication_date, "items": ordered}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def missing_summary_items(items: list[Item], summary_map: dict[str, dict[str, str]]) -> list[Item]:
    return [item for item in items if item.doc_id not in summary_map]
