#!/usr/bin/env python3
"""OCR one Royal Gazette PDF to stdout.

Dates and numbers in the OCR text can be wrong. Use data/items JSON for
วันที่, เล่ม, ตอน, ประเภท, and หน้า.

Examples:
  python scripts/ocr_pdf.py https://ratchakitcha.soc.go.th/documents/133319.pdf
  python scripts/ocr_pdf.py ./local.pdf --max-pages 4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ratchakitcha.ocr import OcrError, download_pdf, ocr_pdf, tools_available  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="official PDF URL or a local PDF path")
    parser.add_argument("--max-pages", type=int, default=4)
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()
    if not tools_available():
        print(
            "Install poppler-utils and tesseract-ocr-tha:\n"
            "  sudo apt-get update && sudo apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-tha",
            file=sys.stderr,
        )
        return 2
    try:
        source = args.source
        if source.startswith("http://") or source.startswith("https://"):
            import tempfile

            with tempfile.TemporaryDirectory(prefix="gazette-pdf-") as temporary:
                pdf_path = Path(temporary) / "document.pdf"
                download_pdf(source, pdf_path)
                text = ocr_pdf(pdf_path, dpi=args.dpi, max_pages=args.max_pages)
        else:
            text = ocr_pdf(Path(source), dpi=args.dpi, max_pages=args.max_pages)
    except OcrError as error:
        print(str(error), file=sys.stderr)
        return 1
    sys.stdout.write(text)
    if text and not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
