"""Telegram and Buttondown notices. Each channel runs only when its secrets exist."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from html import escape
from pathlib import Path

from ratchakitcha.dates import format_thai_date
from ratchakitcha.models import Item

DISCLAIMER_SHORT = (
    "สรุปไม่เป็นทางการ ไม่ใช่คำแนะนำทางกฎหมาย "
    "ต้นฉบับอยู่ที่เว็บไซต์ราชกิจจานุเบกษา"
)

HttpFunc = urllib.request.urlopen


def _secret(name: str) -> str:
    return os.environ.get(name, "").strip()


def telegram_configured() -> bool:
    return bool(_secret("TELEGRAM_BOT_TOKEN") and _secret("TELEGRAM_CHANNEL_ID"))


def buttondown_configured() -> bool:
    return bool(_secret("BUTTONDOWN_API_KEY"))


def empty_state() -> dict:
    return {"telegram_dates": [], "email_dates": []}


def load_state(path: Path) -> dict:
    if not path.exists():
        return empty_state()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "telegram_dates": list(data.get("telegram_dates") or []),
        "email_dates": list(data.get("email_dates") or []),
    }


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "telegram_dates": sorted(set(state.get("telegram_dates") or [])),
        "email_dates": sorted(set(state.get("email_dates") or [])),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plan_notifications(state: dict, bangkok_today: str, new_doc_ids: set[str]) -> dict[str, bool]:
    """At most one Telegram post and one email per Bangkok calendar day.

    A morning run that finds nothing does not mark the day, so the evening run
    can still send. A second run the same day does not send again.
    Email is sent only when this run actually found new document ids.
    """
    has_new = bool(new_doc_ids)
    return {
        "telegram": has_new and bangkok_today not in state.get("telegram_dates", []),
        "email": has_new and bangkok_today not in state.get("email_dates", []),
    }


def _meta(item: Item) -> str:
    bits = [item.category]
    if item.volume or item.part or item.section:
        bits.append(f"เล่ม {item.volume} ตอน {item.part} {item.section}".strip())
    return " · ".join(bit for bit in bits if bit)


def build_telegram_message(items: list[Item], *, page_url: str, digest_date: str) -> str:
    header = f"<b>ราชกิจจานุเบกษา {escape(format_thai_date(digest_date))}</b>"
    lines = [header, f"รายการใหม่ {len(items)} เรื่อง", ""]
    used = "\n".join(lines)
    for item in items:
        block = (
            f'• <a href="{escape(item.url, quote=True)}">{escape(item.title)}</a>\n'
            f"  {escape(_meta(item))}"
        )
        footer = (
            f'\n\n<a href="{escape(page_url, quote=True)}">อ่านทั้งหมดบนเว็บสรุป</a>\n'
            f"{escape(DISCLAIMER_SHORT)}"
        )
        if len(used) + len(block) + len(footer) > 3800:
            break
        lines.append(block)
        used = "\n".join(lines)
    lines.append("")
    lines.append(f'<a href="{escape(page_url, quote=True)}">อ่านทั้งหมดบนเว็บสรุป</a>')
    lines.append(escape(DISCLAIMER_SHORT))
    return "\n".join(lines)


def build_email(items: list[Item], *, page_url: str, digest_date: str) -> tuple[str, str]:
    thai = format_thai_date(digest_date)
    subject = f"ราชกิจจานุเบกษา {thai} — {len(items)} เรื่องใหม่"
    parts = [
        f"# ราชกิจจานุเบกษา {thai}",
        "",
        f"> {DISCLAIMER_SHORT}",
        "",
        f"มีประกาศใหม่ {len(items)} เรื่องในรอบนี้",
        "",
    ]
    for item in items[:15]:
        parts.append(f"- [{item.title}]({item.url}) — {item.category}")
    parts.extend(["", f"[เปิดหน้าสรุป]({page_url})"])
    return subject, "\n".join(parts)


def _post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error


def _patch_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **headers},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error


def send_telegram(text: str, *, token: str | None = None, channel_id: str | None = None) -> None:
    token = (token if token is not None else _secret("TELEGRAM_BOT_TOKEN")).strip()
    channel_id = (channel_id if channel_id is not None else _secret("TELEGRAM_CHANNEL_ID")).strip()
    if not token or not channel_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    result = _post_json(
        url,
        {
            "chat_id": channel_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        {},
    )
    if not result.get("ok", True):
        raise RuntimeError("Telegram rejected the digest message")


def send_buttondown(subject: str, body: str, *, api_key: str | None = None) -> None:
    api_key = (api_key if api_key is not None else _secret("BUTTONDOWN_API_KEY")).strip()
    if not api_key:
        return
    headers = {"Authorization": f"Token {api_key}"}
    created = _post_json(
        "https://api.buttondown.com/v1/emails",
        {"subject": subject, "body": body, "status": "draft"},
        headers,
    )
    email_id = created.get("id")
    if not email_id:
        raise RuntimeError("Buttondown did not return an email id")
    _patch_json(
        f"https://api.buttondown.com/v1/emails/{email_id}",
        {"status": "about_to_send"},
        headers,
    )


def deliver(
    *,
    state: dict,
    bangkok_today: str,
    new_items: list[Item],
    page_url: str,
) -> dict:
    """Send what the plan allows. Returns the state to persist.

    A failed channel is logged and not marked sent, so the next run can retry.
    Missing secrets are skipped with a log line and are not an error.
    """
    plan = plan_notifications(state, bangkok_today, {item.doc_id for item in new_items})
    if not new_items:
        print("[notify] no new documents")
        return state
    digest_date = max(item.date for item in new_items)
    ranked = sorted(new_items, key=lambda item: (-item.importance, item.doc_id))

    if plan["telegram"]:
        if not telegram_configured():
            print("[notify] Telegram secrets not set; skipping")
        else:
            try:
                send_telegram(
                    build_telegram_message(ranked, page_url=page_url, digest_date=digest_date)
                )
                state.setdefault("telegram_dates", []).append(bangkok_today)
                print("[notify] Telegram digest sent")
            except Exception as error:  # noqa: BLE001
                print(f"[notify] Telegram failed: {error}")
    elif bangkok_today in state.get("telegram_dates", []):
        print("[notify] Telegram already sent today")

    if plan["email"]:
        if not buttondown_configured():
            print("[notify] BUTTONDOWN_API_KEY not set; skipping")
        else:
            try:
                subject, body = build_email(ranked, page_url=page_url, digest_date=digest_date)
                send_buttondown(subject, body)
                state.setdefault("email_dates", []).append(bangkok_today)
                print("[notify] Buttondown email queued")
            except Exception as error:  # noqa: BLE001
                print(f"[notify] Buttondown failed: {error}")
    elif bangkok_today in state.get("email_dates", []):
        print("[notify] email already sent today")
    return state
