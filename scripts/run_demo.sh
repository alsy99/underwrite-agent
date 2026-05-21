#!/usr/bin/env bash
set -euo pipefail

API="${API_URL:-http://localhost:8000}"
KEY="${API_KEY:-dev-api-key-change-me}"
FIXTURES="$(cd "$(dirname "$0")/.." && pwd)/data/fixtures"

echo "==> Health check"
curl -s "$API/health" | head -c 200
echo ""

echo "==> Upload SBA policy"
curl -s -X POST "$API/v1/tenants/default/policies" \
  -H "Authorization: Bearer $KEY" \
  -F "title=SBA Policy Seed" \
  -F "file=@$FIXTURES/policies/sba_policy_seed.md"
echo ""

echo "==> Create fraudulent SBA case"
RESP=$(curl -s -X POST "$API/v1/cases" \
  -H "Authorization: Bearer $KEY" \
  -F "vertical=sba_7a" \
  -F "tenant_id=default" \
  -F 'metadata={"business_name":"Acme Consulting LLC","employer":"Acme Consulting LLC","address":"1200 Market Street Suite 400 Wilmington DE","stated_employer":"Acme Consulting LLC"}' \
  -F "documents=@$FIXTURES/sba/fraudulent/form_1919.txt" \
  -F "documents=@$FIXTURES/sba/fraudulent/profit_loss.txt" \
  -F "documents=@$FIXTURES/sba/fraudulent/employment_letter.txt" \
  -F "documents=@$FIXTURES/sba/fraudulent/bank_statement.txt")
echo "$RESP"
CASE_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['case_id'])" 2>/dev/null || echo "")

if [ -z "$CASE_ID" ]; then
  echo "Failed to create case"
  exit 1
fi

echo "==> Poll case $CASE_ID"
for i in $(seq 1 30); do
  STATUS=$(curl -s "$API/v1/cases/$CASE_ID" -H "Authorization: Bearer $KEY")
  STATE=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
  echo "  attempt $i: $STATE"
  if [ "$STATE" = "completed" ] || [ "$STATE" = "failed" ]; then
    echo "$STATUS" | python3 -m json.tool 2>/dev/null || echo "$STATUS"
    break
  fi
  sleep 2
done

echo "==> Audit trail"
curl -s "$API/v1/cases/$CASE_ID/audit" -H "Authorization: Bearer $KEY" | python3 -m json.tool 2>/dev/null | head -80
