"""Phase 2 keyword alerts. Matching only: no payment and no message sending.

Subscriber records are the private data a later job would store outside this
public repository. `data/subscribers.json` is gitignored. The example file
shows the shape. A subscriber matches only when `active` is true and the plan
is a paid tier. Keywords past the plan limit are ignored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ratchakitcha.models import Item

PLAN_LIMITS = {
    "keywords_5": 5,
    "keywords_20": 20,
}


@dataclass
class Subscriber:
    subscriber_id: str
    channel: str
    destination: str
    keywords: list[str] = field(default_factory=list)
    plan: str = "pending"
    active: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> Subscriber:
        return cls(
            subscriber_id=str(data.get("subscriber_id") or ""),
            channel=str(data.get("channel") or ""),
            destination=str(data.get("destination") or ""),
            keywords=list(data.get("keywords") or []),
            plan=str(data.get("plan") or "pending"),
            active=bool(data.get("active")),
        )


@dataclass
class Alert:
    subscriber_id: str
    channel: str
    destination: str
    doc_id: str
    title: str
    matched_keywords: list[str]


def normalize_keyword(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def effective_keywords(subscriber: Subscriber) -> list[str]:
    limit = PLAN_LIMITS.get(subscriber.plan, 0)
    if limit <= 0:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for keyword in subscriber.keywords:
        text = normalize_keyword(keyword)
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def match_keywords(title: str, extra_text: str, keywords: list[str]) -> list[str]:
    haystack = " ".join(f"{title}\n{extra_text or ''}".casefold().split())
    found: list[str] = []
    for keyword in keywords:
        needle = " ".join(keyword.casefold().split())
        if needle and needle in haystack:
            found.append(keyword)
    return found


def find_alerts(
    items: list[Item],
    subscribers: list[Subscriber],
    texts: dict[str, str] | None = None,
) -> list[Alert]:
    """Match new titles and optional OCR text. Inactive and unpaid plans match nothing."""
    texts = texts or {}
    alerts: list[Alert] = []
    for subscriber in subscribers:
        if not subscriber.active or not subscriber.subscriber_id:
            continue
        keywords = effective_keywords(subscriber)
        if not keywords:
            continue
        for item in items:
            matched = match_keywords(item.title, texts.get(item.doc_id, ""), keywords)
            if not matched:
                continue
            alerts.append(
                Alert(
                    subscriber_id=subscriber.subscriber_id,
                    channel=subscriber.channel,
                    destination=subscriber.destination,
                    doc_id=item.doc_id,
                    title=item.title,
                    matched_keywords=matched,
                )
            )
    return alerts


def load_subscribers(path: Path) -> list[Subscriber]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("subscribers", data if isinstance(data, list) else [])
    return [Subscriber.from_dict(row) for row in rows]
