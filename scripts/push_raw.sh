#!/usr/bin/env bash
# Fetch the current Royal Gazette monthly workbook and commit it on main.
#
# Run from any directory. No clone is required. The token is a fine-grained
# PAT with Contents: Read and write on this repository.
#
#   GITHUB_TOKEN=github_pat_... ./scripts/push_raw.sh
#
# Suggested crontab (about ten minutes before the Actions schedule):
#
#   CRON_TZ=Asia/Bangkok
#   20 7 * * *  GITHUB_TOKEN=github_pat_... /path/to/push_raw.sh
#   20 19 * * * GITHUB_TOKEN=github_pat_... /path/to/push_raw.sh
#
# The dated archive commit is marked [skip ci]. The monthly-latest.xlsx commit
# is not, so Actions ingests, builds, deploys, and notifies once.

set -euo pipefail

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "Set GITHUB_TOKEN to a fine-grained PAT with Contents read/write." >&2
  exit 1
fi

REPO="${GITHUB_REPOSITORY:-MrCorinthian/ratchakitcha-digest}"
BRANCH="${GITHUB_BRANCH:-main}"
API="https://api.github.com"
SOURCE_URL="https://apprkj.soc.go.th/report_documents_monthly.php"
UA="ratchakitcha-digest/0.1 (+https://github.com/${REPO}; unofficial digest)"

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT
XLSX="$WORKDIR/monthly.xlsx"

curl -fsS --retry 3 --retry-delay 2 \
  -X POST \
  -d month=0 \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Accept: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*" \
  -A "$UA" \
  -o "$XLSX" \
  "$SOURCE_URL"

python3 - "$XLSX" <<'PY'
import sys
data = open(sys.argv[1], "rb").read(64)
if not data.startswith(b"PK"):
    sys.stderr.write("download is not an xlsx file (missing zip magic PK)\n")
    sys.exit(1)
PY

MONTH=$(TZ=Asia/Bangkok date +%Y-%m)
ARCHIVE_PATH="data/raw/monthly-${MONTH}.xlsx"
LATEST_PATH="data/raw/monthly-latest.xlsx"
ARCHIVE_MESSAGE="Archive monthly Royal Gazette spreadsheet for ${MONTH} [skip ci]"
LATEST_MESSAGE="Update monthly Royal Gazette spreadsheet"

blob_sha() {
  python3 - "$1" <<'PY'
import hashlib
import sys
data = open(sys.argv[1], "rb").read()
print(hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest())
PY
}

remote_sha() {
  local path="$1"
  local body="$WORKDIR/get.json"
  local status
  status=$(curl -sS -o "$body" -w "%{http_code}" \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -H "User-Agent: ${UA}" \
    "$API/repos/${REPO}/contents/${path}?ref=${BRANCH}")
  if [[ "$status" == "404" ]]; then
    echo ""
    return 0
  fi
  if [[ "$status" != "200" ]]; then
    echo "Could not read ${path}: HTTP ${status}" >&2
    python3 - "$body" <<'PY' >&2
import json, sys
try:
    print(json.load(open(sys.argv[1])).get("message", ""))
except Exception:
    print(open(sys.argv[1], encoding="utf-8", errors="replace").read(500))
PY
    return 1
  fi
  python3 - "$body" <<'PY'
import json, sys
print(json.load(open(sys.argv[1])).get("sha") or "")
PY
}

put_file() {
  local path="$1"
  local message="$2"
  local sha="$3"
  local payload="$WORKDIR/put.json"
  local response="$WORKDIR/put-response.json"
  python3 - "$XLSX" "$message" "$BRANCH" "$sha" "$payload" <<'PY'
import base64, json, sys
xlsx, message, branch, sha, outfile = sys.argv[1:]
payload = {
    "message": message,
    "content": base64.b64encode(open(xlsx, "rb").read()).decode("ascii"),
    "branch": branch,
}
if sha:
    payload["sha"] = sha
json.dump(payload, open(outfile, "w", encoding="utf-8"))
PY
  local status
  status=$(curl -sS -o "$response" -w "%{http_code}" \
    -X PUT \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -H "Content-Type: application/json" \
    -H "User-Agent: ${UA}" \
    --data-binary @"$payload" \
    "$API/repos/${REPO}/contents/${path}")
  if [[ "$status" != "200" && "$status" != "201" ]]; then
    echo "Could not write ${path}: HTTP ${status}" >&2
    python3 - "$response" <<'PY' >&2
import json, sys
try:
    print(json.load(open(sys.argv[1])).get("message", ""))
except Exception:
    print(open(sys.argv[1], encoding="utf-8", errors="replace").read(500))
PY
    return 1
  fi
  echo "Committed ${path}"
}

LOCAL_SHA=$(blob_sha "$XLSX")
ARCHIVE_SHA=$(remote_sha "$ARCHIVE_PATH")
LATEST_SHA=$(remote_sha "$LATEST_PATH")

changed=0
if [[ "$ARCHIVE_SHA" != "$LOCAL_SHA" ]]; then
  put_file "$ARCHIVE_PATH" "$ARCHIVE_MESSAGE" "$ARCHIVE_SHA"
  changed=1
else
  echo "Unchanged ${ARCHIVE_PATH}"
fi

if [[ "$LATEST_SHA" != "$LOCAL_SHA" ]]; then
  put_file "$LATEST_PATH" "$LATEST_MESSAGE" "$LATEST_SHA"
  changed=1
else
  echo "Unchanged ${LATEST_PATH}"
fi

if [[ "$changed" == "0" ]]; then
  echo "Spreadsheet already matches main; no commit."
fi
