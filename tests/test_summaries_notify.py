from ratchakitcha.gemini_summary import build_prompt, parse_model_json, summarize_top_items
from ratchakitcha.models import Item
from ratchakitcha.notify import (
    build_telegram_message,
    plan_notifications,
    telegram_configured,
)
from ratchakitcha.summaries import load_summary_map, upsert_summaries


def _item(doc_id: str, importance: int = 90) -> Item:
    return Item(
        doc_id=doc_id,
        title=f"เรื่อง <{doc_id}>",
        date="2026-10-01",
        section="ก",
        volume="143",
        part="61",
        page="1",
        category="กฎหมาย/พ.ร.บ./พ.ร.ก./กฎกระทรวง",
        importance=importance,
        url=f"https://ratchakitcha.soc.go.th/documents/{doc_id}.pdf",
    )


def test_summary_upsert_does_not_overwrite(tmp_path):
    added = upsert_summaries(
        tmp_path,
        {
            "2026-10-01": [
                {
                    "doc_id": "9",
                    "summary": "สรุปเดิม",
                    "affected": "หน่วยงานรัฐ",
                    "generated_by": "cursor-automation",
                }
            ]
        },
    )
    assert added == 1
    added = upsert_summaries(
        tmp_path,
        {
            "2026-10-01": [
                {
                    "doc_id": "9",
                    "summary": "สรุปใหม่ที่ไม่ควรทับ",
                    "affected": "คนอื่น",
                    "generated_by": "gemini",
                },
                {
                    "doc_id": "10",
                    "summary": "สรุปเพิ่ม",
                    "affected": "นายจ้าง",
                    "generated_by": "gemini",
                },
            ]
        },
    )
    assert added == 1
    stored = load_summary_map(tmp_path)
    assert stored["9"]["summary"] == "สรุปเดิม"
    assert stored["9"]["generated_by"] == "cursor-automation"
    assert stored["10"]["summary"] == "สรุปเพิ่ม"


def test_gemini_fills_gaps_without_a_network(tmp_path):
    calls = {"ocr": 0, "gen": 0}

    def ocr(item: Item) -> str:
        calls["ocr"] += 1
        return "เนื้อหาจาก OCR " * 8

    def generate(prompt: str) -> str:
        calls["gen"] += 1
        assert "133319" in prompt or "10" in prompt
        assert "ห้ามใช้คำว่า" in prompt
        return '{"summary":"สรุปจากแบบจำลอง","affected":"ผู้ปฏิบัติตามระเบียบ"}'

    count = summarize_top_items(
        [_item("10")],
        tmp_path,
        api_key="test-key",
        sleep_seconds=0,
        generate=generate,
        ocr_text=ocr,
    )
    assert count == 1
    assert calls == {"ocr": 1, "gen": 1}
    assert summarize_top_items([_item("10")], tmp_path, api_key="", sleep_seconds=0, generate=generate, ocr_text=ocr) == 0
    prompt = build_prompt(_item("10"), "ข้อความ")
    summary, affected = parse_model_json('คำตอบ ```json\n{"summary":"ก","affected":"ข"}\n```')
    assert summary == "ก"
    assert affected == "ข"
    assert "เมตาดาตา" in prompt


def test_notification_plan_and_telegram_text(monkeypatch):
    state = {"telegram_dates": [], "email_dates": []}
    assert plan_notifications(state, "2026-10-02", set()) == {"telegram": False, "email": False}
    assert plan_notifications(state, "2026-10-02", {"1"}) == {"telegram": True, "email": True}
    state["telegram_dates"].append("2026-10-02")
    state["email_dates"].append("2026-10-02")
    assert plan_notifications(state, "2026-10-02", {"2"}) == {"telegram": False, "email": False}

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)
    assert telegram_configured() is False
    text = build_telegram_message(
        [_item("133319")],
        page_url="https://example.test/archive/2026-10-01/",
        digest_date="2026-10-01",
    )
    assert "เรื่อง &lt;133319&gt;" in text
    assert "https://example.test/archive/2026-10-01/" in text
    assert "ไม่ใช่คำแนะนำทางกฎหมาย" in text
    assert "documents/133319.pdf" in text
