#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-https://overleaf-tdkd.onrender.com}"

echo "Botanik API Health Check"
echo "Base URL: $BASE_URL"
echo

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
check "Taxa search Acer" "$BASE_URL/api/botanik/taxa?q=Acer"
check "Taxon detail Berberis vulgaris" "$BASE_URL/api/botanik/taxon/berberis_vulgaris"
check "Photo features high/high" "$BASE_URL/api/botanik/features/photo"
check "Photo features medium/medium" "$BASE_URL/api/botanik/features/photo?visibility=medium&weight=medium"

echo "All Botanik API checks passed."
