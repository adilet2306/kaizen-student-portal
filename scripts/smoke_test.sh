#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"

for path in health ready version instance; do
  echo "Checking ${BASE_URL}/${path}"
  curl --fail --silent --show-error "${BASE_URL}/${path}"
  echo
done
