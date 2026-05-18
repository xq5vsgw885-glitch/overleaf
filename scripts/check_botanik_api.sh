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

echo "All Botanik API checks passed."
