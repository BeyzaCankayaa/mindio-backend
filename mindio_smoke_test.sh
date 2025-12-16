#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-https://mindio-backend.onrender.com}"
EMAIL="${EMAIL:-user10@mindio.com}"
PASSWORD="${PASSWORD:-Test12345!}"
N8N_URL="${N8N_URL:-https://ilydrgn.app.n8n.cloud/webhook/mindio-test}"

echo "BASE=$BASE"
echo "EMAIL=$EMAIL"
echo "N8N_URL=$N8N_URL"

echo
echo "== 1) LOGIN -> TOKEN =="

TOKEN="$(curl -s -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")"

echo "TOKEN OK (len=${#TOKEN})"

echo
echo "== 2) AUTH/ME =="
curl -s "$BASE/auth/me" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo
echo "== 3) PERSONALITY/SUBMIT (DB write) =="
curl -s -X POST "$BASE/personality/submit" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"q1_answer":"18-30","q2_answer":"Kadın","q3_answer":"Stresli","q4_answer":["Uyku","Anksiyete"]}' \
  | python3 -m json.tool

echo
echo "== 4) N8N DIRECT TEST (headers + body_len) =="

TMP_BODY="$(mktemp)"
TMP_HDR="$(mktemp)"

curl -s -D "$TMP_HDR" -o "$TMP_BODY" -X POST "$N8N_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "message":"Bugün stresliyim, tek cümle öneri ver.",
    "history":[],
    "userContext":"AgeRange: 18-30 | Gender: Kadın | Mood: Stresli | Topics: Uyku, Anksiyete"
  }' >/dev/null

echo "--- headers ---"
cat "$TMP_HDR" | sed -n '1,25p'
echo
echo "--- body_len ---"
wc -c < "$TMP_BODY"
echo "--- body_preview ---"
python3 - <<PY
p = open("$TMP_BODY","rb").read()
print(p[:200])
PY

rm -f "$TMP_BODY" "$TMP_HDR"

echo
echo "== 5) /ai/chat (backend -> n8n) =="
curl -s -X POST "$BASE/ai/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Bugün stresliyim, tek cümle öneri ver.","history":[]}' \
  | python3 -m json.tool

echo
echo "== 6) /suggestions/generate (backend -> n8n -> DB) =="
curl -s -X POST "$BASE/suggestions/generate" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool

echo
echo "== 7) /suggestions/daily (same day should be stable) =="

python3 - <<PY
import json, urllib.request

base = "${BASE}"
token = "${TOKEN}"

def get(path):
    req = urllib.request.Request(
        base + path,
        headers={"Authorization": "Bearer " + token}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw.decode("utf-8"))

a = get("/suggestions/daily")
b = get("/suggestions/daily")

print("A id =", a.get("id"))
print("B id =", b.get("id"))
print("SAME_DAY_STABLE =", a.get("id") == b.get("id"))
PY

echo
echo "✅ SMOKE TEST FINISHED"
