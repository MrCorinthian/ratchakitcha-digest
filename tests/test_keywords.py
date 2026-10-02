from ratchakitcha.keywords import Subscriber, find_alerts, load_subscribers, match_keywords
from ratchakitcha.models import Item


def _item(doc_id: str, title: str) -> Item:
    return Item(
        doc_id=doc_id,
        title=title,
        date="2026-10-01",
        url=f"https://ratchakitcha.soc.go.th/documents/{doc_id}.pdf",
    )


def test_match_title_ocr_and_normalization():
    assert match_keywords("ประกาศค่าจ้างขั้นต่ำ", "", ["ค่าจ้างขั้นต่ำ"]) == ["ค่าจ้างขั้นต่ำ"]
    assert match_keywords("ประกาศทั่วไป", "พบคำว่า ผังเมือง ในเนื้อความ", ["ผังเมือง"]) == ["ผังเมือง"]
    assert match_keywords("ไม่มีคำนี้", "", ["ภาษี"]) == []
    assert match_keywords("ค่าจ้าง  ขั้นต่ำ", "", ["ค่าจ้าง ขั้นต่ำ"]) == ["ค่าจ้าง ขั้นต่ำ"]


def test_plan_limit_and_inactive_subscribers(tmp_path):
    paid = Subscriber(
        subscriber_id="s1",
        channel="telegram",
        destination="123",
        keywords=["หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก"],
        plan="keywords_5",
        active=True,
    )
    items = [_item(str(index), f"เรื่อง{word}") for index, word in enumerate(["หนึ่ง", "หก", "อื่น"], start=1)]
    alerts = find_alerts(items, [paid])
    matched = {alert.title for alert in alerts}
    assert any("หนึ่ง" in title for title in matched)
    assert not any("หก" in title for title in matched)

    inactive = Subscriber(
        subscriber_id="s2",
        channel="email",
        destination="a@example.com",
        keywords=["หนึ่ง"],
        plan="keywords_20",
        active=False,
    )
    pending = Subscriber(
        subscriber_id="s3",
        channel="email",
        destination="b@example.com",
        keywords=["หนึ่ง"],
        plan="pending",
        active=True,
    )
    assert find_alerts(items, [inactive, pending]) == []

    path = tmp_path / "subscribers.json"
    path.write_text(
        '{"subscribers":[{"subscriber_id":"s1","channel":"telegram","destination":"1","keywords":["ภาษี"],"plan":"keywords_5","active":true}]}',
        encoding="utf-8",
    )
    loaded = load_subscribers(path)
    assert loaded[0].plan == "keywords_5"
    assert loaded[0].active is True
