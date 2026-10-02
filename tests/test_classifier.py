from pathlib import Path

from ratchakitcha.classify import category_slug, classify, importance_score
from ratchakitcha.models import Item
from ratchakitcha.provinces import PROVINCES, find_provinces
from ratchakitcha.xlsx_source import parse_xlsx

FIXTURE = Path(__file__).parent / "fixtures" / "sample_monthly_2026-10.xlsx"


def _item(title: str, section: str = "ง") -> Item:
    return classify(
        Item(
            doc_id="1",
            title=title,
            date="2026-10-01",
            section=section,
            url="https://ratchakitcha.soc.go.th/documents/1.pdf",
        )
    )


def test_province_list_and_ambiguous_names():
    assert len(PROVINCES) == 77
    assert find_provinces("การแพร่ระบาดของโรค") == []
    assert find_provinces("ประกาศจังหวัดแพร่ เรื่อง ทดสอบ") == ["แพร่"]
    assert find_provinces("ศาลจังหวัดตาก") == ["ตาก"]
    assert find_provinces("กรุงเทพฯ และกทม.") == ["กรุงเทพมหานคร"]
    assert find_provinces("จังหวัดเชียงใหม่และจังหวัดลำพูน") == ["เชียงใหม่", "ลำพูน"]
    assert find_provinces("ศาลจังหวัดธัญบุรี") == []


def test_categories_and_importance_order():
    law = _item("พระราชบัญญัติภาษีเงินได้ พ.ศ. 2569", "ก")
    assert law.category_slug == "finance"
    assert law.importance >= 90

    regulation = _item(
        "ระเบียบคณะกรรมการตรวจเงินแผ่นดิน ว่าด้วยการกำกับการตรวจเงินแผ่นดิน",
        "ก",
    )
    assert regulation.category_slug == "law"
    errata = _item(
        "กระทรวงกลาโหม ขอแก้ไขข้อความคลาดเคลื่อน กฎกระทรวงกำหนดระยะเวลา",
        "ก",
    )
    assert errata.category_slug == "law"
    assert errata.importance < regulation.importance

    labor = _item("ประกาศกระทรวงแรงงาน เรื่อง ค่าจ้างขั้นต่ำจังหวัดระยอง", "ง")
    assert labor.category_slug == "labor"
    assert labor.provinces == ["ระยอง"]

    assert _item("ประกาศเจ้าพนักงานพิทักษ์ทรัพย์ เรื่อง คำสั่งพิทักษ์ทรัพย์เด็ดขาด", "ง พิเศษ").category_slug == "bankruptcy"
    assert _item("พระราชทานเครื่องราชอิสริยาภรณ์", "ข").category_slug == "decoration"
    assert _item("ประกาศสำนักนายกรัฐมนตรี เรื่อง แต่งตั้ง", "ข").category_slug == "decoration"
    assert _item("ประกาศกระทรวงมหาดไทย เรื่อง เปลี่ยนชื่อเทศบาลตำบล", "ง พิเศษ").category_slug == "local"
    assert _item("ประกาศสำนักงานที่ดินจังหวัดประจวบคีรีขันธ์ เรื่อง อาคารชุด", "ง").category_slug == "land"
    assert category_slug("ประกาศกรมการปกครอง", "ง") == "ministry"
    assert (
        category_slug(
            "ประกาศกระทรวงเกษตรและสหกรณ์ เรื่อง กำหนดทางน้ำชลประทานตามพระราชบัญญัติการชลประทานหลวง",
            "ง พิเศษ",
        )
        == "ministry"
    )

    bankruptcy = importance_score("ประกาศเจ้าพนักงานพิทักษ์ทรัพย์", "ง พิเศษ")
    section_kho = importance_score("แต่งตั้ง", "ข")
    assert regulation.importance > section_kho > bankruptcy


def test_fixture_classification():
    items = [classify(item) for item in parse_xlsx(FIXTURE.read_bytes())]
    by_title = {item.title: item for item in items}
    first = next(item for item in items if item.doc_id == "133319")
    assert first.category_slug == "law"
    assert first.importance >= 80
    transport = next(item for item in items if item.title.startswith("ประกาศคณะกรรมการควบคุมการขนส่งทางบกประจำจังหวัดอุบลราชธานี"))
    assert "อุบลราชธานี" in transport.provinces
    assert transport.category_slug == "other"
    bankruptcy = [item for item in items if item.category_slug == "bankruptcy"]
    assert len(bankruptcy) >= 60
    assert max(item.importance for item in items if item.section == "ก") > max(
        item.importance for item in bankruptcy
    )
    assert by_title
