"""Category labels shared by the classifier and the static site."""

from __future__ import annotations

# Classification priority, then display order.
CATEGORIES: tuple[tuple[str, str, str], ...] = (
    (
        "bankruptcy",
        "ล้มละลาย/พิทักษ์ทรัพย์",
        "คำสั่งพิทักษ์ทรัพย์ ล้มละลาย และประกาศเกี่ยวกับคนไร้ความสามารถ",
    ),
    (
        "decoration",
        "เครื่องราชฯ/ยศ",
        "เครื่องราชอิสริยาภรณ์ ฐานันดร และยศ ในราชกิจจานุเบกษาประเภท ข",
    ),
    (
        "labor",
        "แรงงาน/ประกันสังคม",
        "แรงงาน ค่าจ้าง ประกันสังคม และเงินทดแทน",
    ),
    (
        "finance",
        "ภาษี/การคลัง",
        "ภาษี อากร ศุลกากร และประกาศด้านการคลัง",
    ),
    (
        "land",
        "ที่ดิน/ผังเมือง",
        "ที่ดิน ผังเมือง เวนคืน และอาคารชุด",
    ),
    (
        "local",
        "ท้องถิ่น/เทศบัญญัติ",
        "เทศบัญญัติ ข้อบัญญัติ และประกาศเกี่ยวกับเทศบาลหรือองค์การบริหารส่วนท้องถิ่น",
    ),
    (
        "law",
        "กฎหมาย/พ.ร.บ./พ.ร.ก./กฎกระทรวง",
        "พระราชบัญญัติ พระราชกำหนด พระราชกฤษฎีกา กฎกระทรวง ระเบียบ และคำวินิจฉัย",
    ),
    (
        "ministry",
        "ประกาศกระทรวง",
        "ประกาศกระทรวงและประกาศกรมที่ไม่อยู่ในหมวดเฉพาะด้าน",
    ),
    (
        "other",
        "อื่นๆ",
        "ประกาศทั่วไป สมาคม มูลนิธิ และเรื่องที่ไม่ได้จัดเข้าหมวดด้านบน",
    ),
)

LABEL_BY_SLUG = {slug: label for slug, label, _blurb in CATEGORIES}
BLURB_BY_SLUG = {slug: blurb for slug, _label, blurb in CATEGORIES}
SLUGS = tuple(slug for slug, _label, _blurb in CATEGORIES)

SECTION_RANK = {"ก": 0, "ข": 1, "ค": 2, "ง": 3, "ง พิเศษ": 4}
