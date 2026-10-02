You maintain the public repo MrCorinthian/ratchakitcha-digest. Each run adds neutral Thai summaries for the most important new Royal Gazette announcements. Do the work below, then commit and push to the branch `main`. Do not open a pull request unless pushing to main is impossible.

Do not send Telegram or email. GitHub Actions does that after your commit. Do not call Gemini. Do not create accounts. Do not put secrets in the repo. Do not bypass Cloudflare. Pages on ratchakitcha.soc.go.th and apprkj.soc.go.th may show a challenge; leave them alone. PDF files at https://ratchakitcha.soc.go.th/documents/<id>.pdf download directly.

## What to summarize

1. Work from the repository root.
2. If `pdftoppm` or `tesseract` is missing, install them and stop if installation fails:

   sudo apt-get update && sudo apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-tha

3. Decide the publication date. Prefer `data/items/YYYY-MM-DD.json` for today in Asia/Bangkok. If that file does not exist, use the latest `data/items/????-??-??.json`. If there is no items file, stop without committing.
4. Read that file. Sort `items` by `importance` descending. Skip any `doc_id` that already has a non-empty `summary` in `data/summaries/<same-publication-date>.json`. Keep at most 10 remaining items. If none remain, stop without committing.
5. For each chosen item, OCR only that PDF. Do not download any other PDF:

   python scripts/ocr_pdf.py "<item.url>" --max-pages 4

   The script renders the first 4 pages with `pdftoppm -r 200` and reads them with `tesseract -l tha`. If OCR fails or the text is almost empty, skip that item. Do not invent a summary from the title alone.

## How to write the summary

Write in Thai. Neutral, concrete, and short. `summary` is 2 to 4 sentences saying what the announcement does. `affected` is one sentence naming who is affected, with no advice and no "ควร".

Thai digits in the OCR text are often wrong (a check of document 133319 read พ.ศ. ๒๕๖๙ as ๒๕๒๕). Take the date, พ.ศ. year, เล่ม, ตอน, ประเภท, หน้า, and any number that also appears in the items JSON from that JSON, not from OCR. If the OCR text and the JSON disagree, trust the JSON. Do not guess section numbers, money amounts, or dates that you cannot read clearly.

Do not give legal advice. Do not say the announcement is good or bad. Do not claim a penalty, a deadline, or a duty unless the OCR text states it.

## File to commit

Create or update `data/summaries/YYYY-MM-DD.json` for that publication date. Keep every summary already in the file. Add only the doc ids you just summarized. Shape:

```json
{
  "publication_date": "2026-10-01",
  "items": [
    {
      "doc_id": "133319",
      "summary": "สองถึงสี่ประโยค",
      "affected": "กลุ่มที่ได้รับผล เป็นหนึ่งประโยค",
      "generated_by": "cursor-automation"
    }
  ]
}
```

Sort `items` by `doc_id`. UTF-8 JSON, indented by 2 spaces, trailing newline.

Commit only that summary file and push to `main`. Message: `Add Thai summaries for YYYY-MM-DD`. The message must not contain `[skip ci]`, because Actions must rebuild the site and send notifications. If `git status` is clean, do not create an empty commit.
