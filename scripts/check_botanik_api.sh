#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-https://overleaf-tdkd.onrender.com}"

echo "Botanik API Health Check"
echo "Base URL: $BASE_URL"
echo


check_json_field() {
  local label="$1"
  local field="$2"
  local expected="$3"

  python3 - "$label" "$field" "$expected" /tmp/botanik_check_response.json <<'PY'
import json
import sys

label, field, expected, path = sys.argv[1:5]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

value = data
for part in field.split("."):
    value = value[part]

if str(value).lower() != expected.lower():
    print(f"FAIL {label}: expected {field}={expected}, got {value}")
    sys.exit(1)
PY
}

check() {
  local label="$1"
  local url="$2"

  echo "== $label =="
  echo "$url"

  http_code=$(curl -s -o /tmp/botanik_check_response.json -w "%{http_code}" "$url")

  if [ "$http_code" != "200" ]; then
    echo "FAIL HTTP $http_code"
    cat /tmp/botanik_check_response.json
    echo
    exit 1
  fi

  head -c 300 /tmp/botanik_check_response.json
  echo
  echo "OK"
  echo
}

check "Health" "$BASE_URL/api/botanik/health"
check "Taxa search Acer standard" "$BASE_URL/api/botanik/taxa?q=Acer"
check_json_field "Taxa search Acer standard" "include_stubs" "false"
check_json_field "Taxa search Acer standard" "count" "2"

check "Taxa search Acer with stubs" "$BASE_URL/api/botanik/taxa?q=Acer&include_stubs=1"
check_json_field "Taxa search Acer with stubs" "include_stubs" "true"
check_json_field "Taxa search Acer with stubs" "count" "5"
check "Taxon detail Berberis vulgaris" "$BASE_URL/api/botanik/taxon/berberis_vulgaris"
check "Photo features high/high" "$BASE_URL/api/botanik/features/photo"
check "Photo features medium/medium" "$BASE_URL/api/botanik/features/photo?visibility=medium&weight=medium"


echo "== Local DB quality: active direct taxa have features =="
QC_COUNT=$(sqlite3 database/botanik_v4_0_production_ready.db "
WITH taxon_feature_counts AS (
  SELECT
    t.taxon_id,
    t.rank,
    t.status,
    COUNT(f.feature_id) AS feature_count
  FROM botanik_taxa t
  LEFT JOIN botanik_features f ON f.taxon_id = t.taxon_id
  WHERE t.status = 'active'
    AND t.rank IN ('species','genus','hybrid')
  GROUP BY t.taxon_id
)
SELECT COUNT(*)
FROM taxon_feature_counts
WHERE feature_count = 0;
")

if [ "$QC_COUNT" != "0" ]; then
  echo "FAIL: active species/genus/hybrid without diagnostic features: $QC_COUNT"
  exit 1
fi

echo "OK"
echo

echo "All Botanik API checks passed."
