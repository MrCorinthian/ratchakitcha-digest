"""Optional Gemini Flash-Lite summaries for the highest-ranked items.

Used only when GEMINI_API_KEY is set. Existing summaries are left untouched.
Requests are spaced to stay under the free-tier rate of about 15 per minute.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from ratchakitcha.models import Item
from ratchakitcha.summaries import upsert_summaries

DEFAULT_MODEL = "gemini-2.5-flash-lite"
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)

GenerateFunc = Callable[[str], str]
OcrFunc = Callable[[Item], str]


def gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def build_prompt(item: Item, ocr_text: str) -> str:
    clipped = ocr_text.strip()[:12000]
    return (
        "คุณสรุปประกาศในราชกิจจานุเบกษาเป็นภาษาไทยอย่างเป็นกลาง "
        "ตอบเป็น JSON เท่านั้น ในรูป {\"summary\":\"...\",\"affected\":\"...\"}\n"
        "summary คือ 2 ถึง 4 ประโยค บอกว่าประกาศนี้ทำอะไร\n"
        "affected คือหนึ่งประโยคขึ้นต้นด้วยกลุ่มคนหรือองค์กรที่ได้รับผล\n"
        "ห้ามให้คำแนะนำทางกฎหมาย และห้ามใช้คำว่า ควร\n"
        "ตัวเลขไทยจาก OCR อาจผิด ให้ใช้วันที่ เล่ม ตอน หน้า และเลขจากเมตาดาตาเท่านั้น "
        "ถ้า OCR ไม่มีเนื้อหาเพียงพอ ให้ตอบ summary ว่าง\n\n"
        f"เลขเอกสาร: {item.doc_id}\n"
        f"ชื่อเรื่อง: {item.title}\n"
        f"วันที่: {item.date}\n"
        f"เล่ม: {item.volume} ตอน: {item.part} ประเภท: {item.section} หน้า: {item.page}\n"
        f"หมวด: {item.category}\n\n"
        "ข้อความ OCR:\n"
        f"{clipped}\n"
    )


def parse_model_json(raw: str) -> tuple[str, str]:
    match = _JSON_OBJECT.search(raw or "")
    if not match:
        return "", ""
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return "", ""
    summary = str(payload.get("summary") or "").strip()
    affected = str(payload.get("affected") or "").strip()
    return summary, affected


def default_generate(prompt: str, *, model: str, api_key: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    body = json.dumps(
        {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 512},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Gemini HTTP {error.code}: {detail}") from error
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    return "\n".join(str(part.get("text") or "") for part in parts)


def summarize_top_items(
    items: list[Item],
    summaries_dir: Path,
    *,
    api_key: str | None = None,
    limit: int = 10,
    sleep_seconds: float = 5.0,
    generate: GenerateFunc | None = None,
    ocr_text: OcrFunc | None = None,
    model: str | None = None,
) -> int:
    key = (api_key if api_key is not None else gemini_api_key()).strip()
    if not key:
        print("[summary] GEMINI_API_KEY is not set; title-only digest")
        return 0
    chosen_model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    queue = list(items)[:limit]
    if not queue:
        print("[summary] no items left to summarize")
        return 0

    def _ocr(item: Item) -> str:
        if ocr_text is not None:
            return ocr_text(item)
        from ratchakitcha.ocr import OcrError, ocr_url, tools_available

        if not tools_available():
            raise OcrError("OCR tools are not installed")
        return ocr_url(item.url, max_pages=4)

    def _generate(prompt: str) -> str:
        if generate is not None:
            return generate(prompt)
        return default_generate(prompt, model=chosen_model, api_key=key)

    rows_by_date: dict[str, list[dict[str, str]]] = {}
    for index, item in enumerate(queue):
        if index and sleep_seconds:
            time.sleep(sleep_seconds)
        try:
            text = _ocr(item)
        except Exception as error:  # noqa: BLE001 - one PDF should not stop the digest
            print(f"[summary] OCR skipped {item.doc_id}: {error}")
            continue
        if len(text.strip()) < 40:
            print(f"[summary] OCR too short for {item.doc_id}")
            continue
        try:
            raw = _generate(build_prompt(item, text))
        except Exception as error:  # noqa: BLE001
            print(f"[summary] Gemini skipped {item.doc_id}: {error}")
            continue
        summary, affected = parse_model_json(raw)
        if not summary:
            print(f"[summary] empty summary for {item.doc_id}")
            continue
        rows_by_date.setdefault(item.date, []).append(
            {
                "doc_id": item.doc_id,
                "summary": summary,
                "affected": affected,
                "generated_by": "gemini",
            }
        )
        print(f"[summary] summarized {item.doc_id}")
    return upsert_summaries(summaries_dir, rows_by_date)
