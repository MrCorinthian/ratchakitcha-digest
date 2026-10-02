# Royal Gazette daily digest

Unofficial daily digest of new announcements in the Thai Royal Gazette (ราชกิจจานุเบกษา). A GitHub Actions job fetches the public monthly spreadsheet, classifies each item with rules, builds a static Thai site, and can post one Telegram message and one email per day. Summaries are optional.

This is not legal advice and it is not a government website. The official text is the PDF on [ราชกิจจานุเบกษา](https://ratchakitcha.soc.go.th/).

## What the job does

Twice a day, at 00:30 and 12:30 UTC (07:30 and 19:30 Bangkok), and when someone runs the workflow by hand:

1. `POST https://apprkj.soc.go.th/report_documents_monthly.php` with `month=0` downloads the current month's Excel file (date, title, เล่ม, ตอน, ประเภท, หน้า, URL). A second request uses the previous month number. When that response is the same file, it is ignored.
2. The homepage listing on `https://apprkj.soc.go.th/` is parsed so the last days of the previous month are not missed when the spreadsheet has already rolled over. Items that show up late are merged into the publication date they belong to.
3. Items are stored in `data/items/YYYY-MM-DD.json`, deduped by the PDF document id. Dates and numbers come from the spreadsheet when both sources have the same document.
4. A rule-based classifier sets a category, an importance score, and province tags. No paid API is required.
5. If `data/summaries/YYYY-MM-DD.json` exists, those summaries are shown. If `GEMINI_API_KEY` is set, Gemini 2.5 Flash-Lite fills summaries for up to 10 top items that do not have one yet. Otherwise the page is a title-only digest.
6. The static site is deployed to GitHub Pages. RSS and Atom feeds are included.
7. If the matching secrets exist, and this run found new document ids, and that channel has not already sent today (Bangkok date), the job sends one Telegram channel post and one Buttondown email. Missing secrets are skipped.

The HTML pages of `ratchakitcha.soc.go.th` are behind a Cloudflare challenge. This project does not try to pass that challenge. Direct PDF links and the apprkj spreadsheet are the sources. If the spreadsheet request itself is challenged, the job fails and says so.

A GitHub-hosted run on 2 October 2026 downloaded the October workbook: 139 documents, all dated 1 October 2026. The homepage listing was challenged from that runner, so the job kept the spreadsheet and still built the site.

## Categories

กฎหมาย/พ.ร.บ./พ.ร.ก./กฎกระทรวง, ประกาศกระทรวง, ภาษี/การคลัง, แรงงาน/ประกันสังคม, ที่ดิน/ผังเมือง, ล้มละลาย/พิทักษ์ทรัพย์, เครื่องราชฯ/ยศ, ท้องถิ่น/เทศบัญญัติ, อื่นๆ.

Section ก and ข, and laws or regulations, sort above routine notices. Province names are read from the title. Very short names such as แพร่ and เลย match only in `จังหวัด…` or `จ.…`, so ordinary words like การแพร่ are not tagged.

## Local use

Python 3.11 or newer. The runtime uses the standard library. Tests need pytest.

```bash
python -m pip install pytest
python -m pytest
```

Preview the checked-in October 2026 spreadsheet without contacting the network:

```bash
python scripts/build_from_fixture.py --out /tmp/gazette-site
python -m http.server 8765 --directory /tmp/gazette-site/site
```

OCR one official PDF (needs `poppler-utils` and `tesseract-ocr-tha`):

```bash
sudo apt-get update && sudo apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-tha
python scripts/ocr_pdf.py https://ratchakitcha.soc.go.th/documents/133319.pdf --max-pages 4
```

Thai digits in that OCR text are sometimes wrong. The digest takes dates and numbers from the spreadsheet, not from OCR.

Run a real fetch from a machine that can reach apprkj:

```bash
PYTHONPATH=src python scripts/run_digest.py --no-notify
```

## Data files

`data/items/YYYY-MM-DD.json` is one publication date. `data/summaries/YYYY-MM-DD.json` holds optional Thai summaries (`summary`, `affected`, `generated_by`). `data/state/notifications.json` records which Bangkok dates already produced a Telegram post or an email. `data/subscribers.example.json` is the phase-2 shape for keyword alerts. Real subscriber records belong in `data/subscribers.json`, which is gitignored. Payment is not implemented. Matching lives in `src/ratchakitcha/keywords.py`.

## Secrets

Add these under Settings → Secrets and variables → Actions. Leave a secret unset to disable that feature. Never commit a token.

| Secret | When it is set |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Bot API token from BotFather. Also set `TELEGRAM_CHANNEL_ID`. |
| `TELEGRAM_CHANNEL_ID` | Channel `@name` or numeric id such as `-100…`. The bot must be an admin that can post. |
| `BUTTONDOWN_API_KEY` | Buttondown API token with permission to send email. One email per Bangkok day, only when there are new items. |
| `GEMINI_API_KEY` | Google AI Studio key. Uses `gemini-2.5-flash-lite`. Free-tier requests may be used by Google to improve products; the text is public gazette data. |

`GEMINI_MODEL` can override the model. It is set in the workflow, not as a secret.

## What you need to do

### 1. Let Actions write, then turn on Pages

1. On GitHub, open this repository → **Settings → Actions → General → Workflow permissions**.
2. Choose **Read and write permissions** so the digest job can commit `data/items`.
3. If `main` is protected, allow GitHub Actions to push, or add a bypass for `github-actions[bot]`. The data commit message contains `[skip ci]` so it does not start another run.
4. Open **Settings → Pages → Build and deployment**.
5. Set **Source** to **GitHub Actions**. Do not choose **Deploy from a branch**.
6. After the first successful run on `main`, the site is published at `https://mrcorinthian.github.io/ratchakitcha-digest/`.
7. You can start that run yourself: **Actions → Daily digest → Run workflow**.

The workflow uploads a `site` artifact on every run, including a manual run from another branch. Deployment to Pages happens only from `main`.

### 2. Add secrets only for the channels you want

1. Create a Telegram bot with [@BotFather](https://t.me/BotFather) and a channel. Add the bot as an administrator that can post messages. Put the token and the channel id in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHANNEL_ID`.
2. Create a free Buttondown newsletter (the API is the free path; their RSS-to-email add-on is paid). Create an API key that can send email. Put it in `BUTTONDOWN_API_KEY`.
3. Optional: create a Gemini API key in Google AI Studio and save it as `GEMINI_API_KEY`. Without it, and without the Cursor automation below, the site still lists titles, categories, and official PDF links.

Nothing is posted or emailed until both the secret exists and a run finds new document ids. A second run on the same Bangkok date does not send again.

### 3. Create the Cursor Automation

Summaries are written by a scheduled cloud agent. The digest works before you create it.

1. Open [cursor.com/automations](https://cursor.com/automations).
2. Create an automation. The trigger is a schedule, not a GitHub event.
3. Cron expression, including the timezone prefix:

   ```
   CRON_TZ=Asia/Bangkok 0 9 * * *
   ```

   That is 09:00 in Bangkok every day. Cursor may start the run later, but not earlier.
4. Scheduled triggers do not attach a repository unless you pick one. Choose `github.com/MrCorinthian/ratchakitcha-digest` and branch `main`. The agent has to commit on that branch.
5. Paste the entire file [`AUTOMATION_PROMPT.md`](AUTOMATION_PROMPT.md) into the prompt.
6. Do not enable Slack or pull-request comment tools. The agent needs a terminal, network access, and git push so it can install Tesseract, download the chosen PDFs, and push `data/summaries/YYYY-MM-DD.json`.
7. Save the automation and leave it enabled.
8. The commit message in that prompt must not contain `[skip ci]`. The push rebuilds the site and sends the daily notifications.

Do not put the Telegram token, the Buttondown key, or the Gemini key in the automation prompt.

---

# สรุปรายวันราชกิจจานุเบกษา

เว็บสรุปรายวันอย่างไม่เป็นทางการของประกาศในราชกิจจานุเบกษา ไม่ใช่คำแนะนำทางกฎหมาย และไม่ใช่เว็บไซต์ของหน่วยงานรัฐ ต้นฉบับอยู่ที่ไฟล์ PDF บน [ราชกิจจานุเบกษา](https://ratchakitcha.soc.go.th/)

## ระบบทำงานอย่างไร

GitHub Actions ทำงานวันละสองครั้ง เวลา 07:30 และ 19:30 ตามเวลาประเทศไทย และเมื่อกดรันเอง

1. ดึงไฟล์ Excel รายเดือนจาก `POST https://apprkj.soc.go.th/report_documents_monthly.php` ด้วย `month=0` แล้วลองขอเดือนก่อนหน้าอีกหนึ่งครั้ง ถ้าได้ไฟล์เดิมจะทิ้ง
2. อ่านรายการบนหน้าแรกของ apprkj เพื่อไม่ให้วันท้ายเดือนที่แล้วยังค้างอยู่ในหน้ารายการหลุดไปตอนขึ้นเดือนใหม่ เรื่องที่มาทีหลังจะถูกใส่เข้าวันที่ประกาศของเรื่องนั้น
3. เก็บรายการใน `data/items/YYYY-MM-DD.json` และตัดซ้ำด้วยเลขเอกสารใน URL ของ PDF วันที่และตัวเลขใช้ค่าจาก Excel เมื่อมีทั้งสองแหล่ง
4. จัดหมวด ให้คะแนนความสำคัญ และติดแท็กจังหวัดจากชื่อเรื่อง โดยไม่ใช้ API ที่เสียเงิน
5. ถ้ามี `data/summaries/YYYY-MM-DD.json` จะแสดงสรุปนั้น ถ้ามี `GEMINI_API_KEY` จะให้ Gemini 2.5 Flash-Lite สรุปไม่เกิน 10 เรื่องสำคัญที่ยังไม่มีสรุป ถ้าไม่มีทั้งสองอย่าง หน้าเว็บจะเป็นรายการชื่อเรื่อง
6. สร้างเว็บนิ่งภาษาไทย พร้อมฟีด RSS และ Atom แล้วขึ้น GitHub Pages
7. ถ้ามี secret ของช่องนั้น และรอบนี้มีเอกสารใหม่ และวันนั้นตามเวลาประเทศไทยยังไม่ได้ส่ง จะส่ง Telegram หนึ่งข้อความ และอีเมล Buttondown หนึ่งฉบับ ถ้าไม่มี secret จะข้ามไปเงียบ ๆ

หน้า HTML ของ ratchakitcha.soc.go.th ติด Cloudflare โปรเจกต์นี้ไม่พยายามผ่าน challenge นั้น ถ้าตัวไฟล์ Excel ถูก challenge งานจะล้มและบอกเหตุผล

รันบน GitHub Actions เมื่อ 2 ตุลาคม 2026 ดึงสมุดงานเดือนตุลาคมได้ 139 ฉบับ ลงวันที่ 1 ตุลาคม 2026 ทั้งหมด หน้ารายการหน้าแรกติด challenge จาก runner นั้น งานจึงใช้เฉพาะไฟล์ Excel และยังสร้างเว็บได้

## หมวด

กฎหมาย/พ.ร.บ./พ.ร.ก./กฎกระทรวง, ประกาศกระทรวง, ภาษี/การคลัง, แรงงาน/ประกันสังคม, ที่ดิน/ผังเมือง, ล้มละลาย/พิทักษ์ทรัพย์, เครื่องราชฯ/ยศ, ท้องถิ่น/เทศบัญญัติ, อื่นๆ

ประเภท ก และ ข รวมถึงกฎหมายและระเบียบ จะอยู่ด้านบนกว่าประกาศประจำวัน ชื่อจังหวัดที่สั้นและไปปนกับคำทั่วไป เช่น แพร่ และ เลย จะจับเฉพาะเมื่อเขียนว่า `จังหวัด…` หรือ `จ.…`

## รันในเครื่อง

ใช้ Python 3.11 ขึ้นไป โค้ดที่รันจริงใช้ไลบรารีมาตรฐาน การทดสอบใช้ pytest

```bash
python -m pip install pytest
python -m pytest
```

ดูตัวอย่างจากไฟล์ Excel เดือนตุลาคม 2569 ที่เก็บไว้ในเทสต์ โดยไม่ต่อเน็ต:

```bash
python scripts/build_from_fixture.py --out /tmp/gazette-site
python -m http.server 8765 --directory /tmp/gazette-site/site
```

อ่านภาพ PDF หนึ่งไฟล์ด้วย OCR:

```bash
sudo apt-get update && sudo apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-tha
python scripts/ocr_pdf.py https://ratchakitcha.soc.go.th/documents/133319.pdf --max-pages 4
```

ตัวเลขไทยจาก OCR อาจผิด ระบบใช้วันที่และตัวเลขจาก Excel

ดึงข้อมูลจริงจากเครื่องที่เข้า apprkj ได้:

```bash
PYTHONPATH=src python scripts/run_digest.py --no-notify
```

## ไฟล์ข้อมูล

`data/items/YYYY-MM-DD.json` คือรายการของวันที่ประกาศ `data/summaries/YYYY-MM-DD.json` คือสรุปภาษาไทย (`summary`, `affected`, `generated_by`) `data/state/notifications.json` จำว่าวันนี้ส่ง Telegram หรืออีเมลแล้วหรือยัง `data/subscribers.example.json` เป็นตัวอย่างโครงผู้รับแจ้งเตือนตามคำค้นสำหรับเฟสถัดไป ยังไม่มีการรับเงิน ตัวจับคู่คำค้นอยู่ใน `src/ratchakitcha/keywords.py` ไฟล์ผู้ใช้จริงชื่อ `data/subscribers.json` และถูก gitignore

## Secrets

ใส่ที่ Settings → Secrets and variables → Actions ไม่ใส่ secret หมายถึงปิดฟีเจอร์นั้น อย่าคอมมิตโทเคน

| Secret | ใช้เมื่อ |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | โทเคนบอทจาก BotFather ต้องคู่กับ `TELEGRAM_CHANNEL_ID` |
| `TELEGRAM_CHANNEL_ID` | ชื่อช่อง `@name` หรือเลข เช่น `-100…` บอทต้องเป็นแอดมินที่โพสต์ได้ |
| `BUTTONDOWN_API_KEY` | คีย์ API ของ Buttondown ที่ส่งอีเมลได้ ส่งวันละหนึ่งฉบับตามเวลาประเทศไทย และเฉพาะวันที่เอกสารใหม่ |
| `GEMINI_API_KEY` | คีย์จาก Google AI Studio ใช้โมเดล `gemini-2.5-flash-lite` โควตาฟรีอาจถูก Google นำไปปรับปรุงบริการ ข้อมูลเป็นประกาศสาธารณะ |

## สิ่งที่เจ้าของต้องทำ

### 1. ให้ Actions เขียนไฟล์ แล้วเปิด Pages

1. เปิดรีโปบน GitHub → **Settings → Actions → General → Workflow permissions**
2. เลือก **Read and write permissions** เพื่อให้งานคอมมิต `data/items` ได้
3. ถ้า branch `main` ถูกล็อก ให้ GitHub Actions พุชได้ หรือยกเว้น `github-actions[bot]` ข้อความคอมมิตมี `[skip ci]` จึงไม่เรียกงานซ้ำ
4. เปิด **Settings → Pages → Build and deployment**
5. ตั้ง **Source** เป็น **GitHub Actions** ไม่ใช้ **Deploy from a branch**
6. หลังรันบน `main` สำเร็จครั้งแรก เว็บอยู่ที่ `https://mrcorinthian.github.io/ratchakitcha-digest/`
7. กดรันเองได้ที่ **Actions → Daily digest → Run workflow**

ทุกครั้งที่รันจะมี artifact ชื่อ `site` รวมรันจาก branch อื่น การขึ้น Pages จริงเกิดเฉพาะจาก `main`

### 2. ใส่ secret เฉพาะช่องที่ใช้

1. สร้างบอท Telegram กับ [@BotFather](https://t.me/BotFather) และสร้างช่อง ตั้งบอทเป็นแอดมินที่โพสต์ข้อความได้ ใส่โทเคนและรหัสช่องใน `TELEGRAM_BOT_TOKEN` กับ `TELEGRAM_CHANNEL_ID`
2. สร้างจดหมายข่าว Buttondown แผนฟรี แล้วสร้าง API key ที่ส่งอีเมลได้ ใส่ใน `BUTTONDOWN_API_KEY` ไม่ใช้ส่วนเสริม RSS-to-email ที่เสียเงิน
3. ถ้าต้องการสรุปจาก Gemini ให้สร้างคีย์ใน Google AI Studio แล้วเก็บเป็น `GEMINI_API_KEY` ถ้าไม่ใส่ และยังไม่สร้าง Cursor Automation ด้านล่าง เว็บยังแสดงชื่อเรื่อง หมวด และลิงก์ PDF ทางการ

ระบบจะส่งก็ต่อเมื่อมี secret และรอบนั้นพบเอกสารใหม่ รันครั้งที่สองในวันเดียวกันตามเวลาประเทศไทยจะไม่ส่งซ้ำ

### 3. สร้าง Cursor Automation

สรุปภาษาไทยเขียนโดย cloud agent ตามตาราง เว็บใช้งานได้ก่อนสร้าง automation นี้

1. เปิด [cursor.com/automations](https://cursor.com/automations)
2. สร้าง automation ทริกเกอร์เป็นตารางเวลา ไม่ใช่อีเวนต์ GitHub
3. ใส่ cron พร้อมเขตเวลา:

   ```
   CRON_TZ=Asia/Bangkok 0 9 * * *
   ```

   คือทุกวัน 09:00 เวลาประเทศไทย Cursor อาจเริ่มช้ากว่านี้ แต่จะไม่เริ่มก่อนเวลา
4. ทริกเกอร์แบบ cron จะไม่ผูกกับรีโปเอง ต้องเลือก `github.com/MrCorinthian/ratchakitcha-digest` และ branch `main` เพื่อให้เอเจนต์คอมมิตได้
5. วางเนื้อหาทั้งไฟล์ [`AUTOMATION_PROMPT.md`](AUTOMATION_PROMPT.md) ลงช่องพรอมป์
6. ไม่ต้องเปิดเครื่องมือ Slack หรือคอมเมนต์ใน pull request เอเจนต์ต้องใช้เทอร์มินัล เน็ต และ git push เพื่อติดตั้ง Tesseract ดาวน์โหลด PDF ที่เลือก และพุช `data/summaries/YYYY-MM-DD.json`
7. บันทึกแล้วเปิดใช้ automation
8. ข้อความคอมมิตในพรอมป์นั้นต้องไม่มี `[skip ci]` การพุชจะสั่งให้ Actions สร้างเว็บใหม่และส่งแจ้งเตือนของวันนั้น

อย่าใส่โทเคน Telegram, คีย์ Buttondown, หรือคีย์ Gemini ลงในพรอมป์
