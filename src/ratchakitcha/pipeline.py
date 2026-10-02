"""One digest run: fetch, classify, summarize when a key exists, build, notify."""

from __future__ import annotations

import json
from pathlib import Path

from ratchakitcha.classify import classify
from ratchakitcha.dates import bangkok_now
from ratchakitcha.fetch import fetch_items
from ratchakitcha.gemini_summary import gemini_api_key, summarize_top_items
from ratchakitcha.notify import deliver, load_state, save_state
from ratchakitcha.site import build_site, site_url
from ratchakitcha.store import known_doc_ids, load_all, merge_items, sort_items
from ratchakitcha.summaries import load_summary_map


def run(
    root: Path,
    *,
    fetch: bool = True,
    summarize: bool = True,
    notify: bool = True,
) -> set[str]:
    root = root.resolve()
    items_dir = root / "data" / "items"
    summaries_dir = root / "data" / "summaries"
    state_path = root / "data" / "state" / "notifications.json"
    items_dir.mkdir(parents=True, exist_ok=True)

    new_ids: set[str] = set()
    if fetch:
        fetched = [classify(item) for item in fetch_items()]
        new_ids = merge_items(items_dir, fetched)
        print(f"[store] {len(new_ids)} new document ids")
    else:
        print("[fetch] offline; using data/items already on disk")

    days = load_all(items_dir)
    if summarize and days:
        latest = max(days)
        summary_map = load_summary_map(summaries_dir)
        top = sort_items(days[latest])[:10]
        missing = [item for item in top if item.doc_id not in summary_map]
        if gemini_api_key():
            summarize_top_items(missing, summaries_dir)
        elif missing:
            print("[summary] no Gemini key and no summary file for the top items; title-only digest")
        else:
            print("[summary] top items already have summaries")

    site_dir = build_site(root)
    print(f"[site] wrote {site_dir}")

    if notify and fetch:
        days = load_all(items_dir)
        new_items = [item for items in days.values() for item in items if item.doc_id in new_ids]
        state = load_state(state_path)
        before = json.dumps(state, sort_keys=True)
        today = bangkok_now().date().isoformat()
        if new_items:
            digest_date = max(item.date for item in new_items)
            page_url = f"{site_url()}/archive/{digest_date}/"
        else:
            page_url = site_url() + "/"
        state = deliver(
            state=state,
            bangkok_today=today,
            new_items=new_items,
            page_url=page_url,
        )
        if json.dumps(state, sort_keys=True) != before:
            save_state(state_path, state)
    return new_ids


def stored_ids(root: Path) -> set[str]:
    return known_doc_ids(root / "data" / "items")
