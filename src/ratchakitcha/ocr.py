"""OCR a gazette PDF with pdftoppm and tesseract -l tha.

Body text in these PDFs uses legacy non-Unicode fonts, so pdftotext is not
usable. Thai digits in the OCR text are sometimes wrong; callers must take
dates, volumes, parts, and page numbers from the spreadsheet metadata.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ratchakitcha.http_client import request
from ratchakitcha.xlsx_source import doc_id_from_url, official_pdf


class OcrError(RuntimeError):
    pass


def tools_available() -> bool:
    return shutil.which("pdftoppm") is not None and shutil.which("tesseract") is not None


def download_pdf(url: str, destination: Path) -> None:
    doc_id = doc_id_from_url(url)
    if not doc_id:
        raise OcrError("only https://ratchakitcha.soc.go.th/documents/<id>.pdf can be downloaded")
    status, body, _content_type = request(official_pdf(doc_id), timeout=60)
    if status != 200 or not body.startswith(b"%PDF"):
        raise OcrError(f"PDF {doc_id} returned HTTP {status}")
    destination.write_bytes(body)


def ocr_pdf(
    pdf_path: Path,
    *,
    dpi: int = 200,
    max_pages: int = 4,
    lang: str = "tha",
) -> str:
    if not tools_available():
        raise OcrError("pdftoppm and tesseract -l tha are required")
    if dpi < 72 or dpi > 300:
        raise OcrError("dpi must stay between 72 and 300")
    if max_pages < 1 or max_pages > 8:
        raise OcrError("max_pages must stay between 1 and 8")

    with tempfile.TemporaryDirectory(prefix="gazette-ocr-") as temporary:
        prefix = str(Path(temporary) / "page")
        render = subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r",
                str(dpi),
                "-f",
                "1",
                "-l",
                str(max_pages),
                str(pdf_path),
                prefix,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if render.returncode != 0:
            raise OcrError(render.stderr.strip() or "pdftoppm failed")
        pages = sorted(Path(temporary).glob("page*.png"))
        if not pages:
            raise OcrError("pdftoppm produced no pages")
        chunks: list[str] = []
        for page in pages:
            result = subprocess.run(
                ["tesseract", str(page), "stdout", "-l", lang, "--psm", "6"],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise OcrError(result.stderr.strip() or f"tesseract failed on {page.name}")
            text = result.stdout.strip()
            if text:
                chunks.append(text)
    return "\n\n".join(chunks)


def ocr_url(url: str, *, dpi: int = 200, max_pages: int = 4) -> str:
    with tempfile.TemporaryDirectory(prefix="gazette-pdf-") as temporary:
        pdf_path = Path(temporary) / "document.pdf"
        download_pdf(url, pdf_path)
        return ocr_pdf(pdf_path, dpi=dpi, max_pages=max_pages)
