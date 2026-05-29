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

check_json_field_nonempty() {
  local label="$1"
  local field="$2"

  python3 - "$label" "$field" /tmp/botanik_check_response.json <<'PY'
import json, sys

label, field, path = sys.argv[1:4]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

value = data
for part in field.split("."):
    value = value[part]

if not str(value).strip():
    print(f"FAIL {label}: {field} is empty")
    sys.exit(1)
PY
}

get_response_count() {
  python3 -c "import json; d=json.load(open('/tmp/botanik_check_response.json')); print(d['count'])"
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
check_json_field_nonempty "Health" "release.version"
check_json_field_nonempty "Health" "release.release_stage"

check "Taxa search Acer standard" "$BASE_URL/api/botanik/taxa?q=Acer"
check_json_field "Taxa search Acer standard" "include_stubs" "false"
ACER_STD_COUNT=$(get_response_count)

check "Taxa search Acer with stubs" "$BASE_URL/api/botanik/taxa?q=Acer&include_stubs=1"
check_json_field "Taxa search Acer with stubs" "include_stubs" "true"
ACER_STUB_COUNT=$(get_response_count)

echo "== Acer relational count check =="
python3 - "$ACER_STD_COUNT" "$ACER_STUB_COUNT" <<'PY'
import sys
std, stub = int(sys.argv[1]), int(sys.argv[2])
if std <= 0:
    print(f"FAIL Acer standard count must be > 0, got {std}")
    sys.exit(1)
if stub < std:
    print(f"FAIL Acer stubs count ({stub}) must be >= standard count ({std})")
    sys.exit(1)
print(f"OK standard={std}, with_stubs={stub}")
PY
echo

check "Taxon detail Berberis vulgaris" "$BASE_URL/api/botanik/taxon/berberis_vulgaris"
check "Photo features high/high" "$BASE_URL/api/botanik/features/photo"
check "Photo features medium/medium" "$BASE_URL/api/botanik/features/photo?visibility=medium&weight=medium"

echo "== P0.2: critical taxa excluded from standard search =="
check "P0.2 festuca_rubra not in standard" "$BASE_URL/api/botanik/taxa?q=festuca_rubra"
check_json_field "P0.2 festuca_rubra" "count" "0"
check "P0.2 ranunculus_auricomus not in standard" "$BASE_URL/api/botanik/taxa?q=ranunculus_auricomus"
check_json_field "P0.2 ranunculus_auricomus" "count" "0"


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
