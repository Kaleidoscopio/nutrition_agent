#!/usr/bin/env bash
set -euo pipefail

JSON_DIR="/home/droque/.hermes/data/food-diary/entries"
PYTHON_BIN="/usr/bin/python3"
IMPORT_SCRIPT="/home/droque/.hermes/scripts/import_meals.py"

cd "$JSON_DIR"

latest_json="$(ls -t *.json 2>/dev/null | head -n 1 || true)"

if [[ -z "${latest_json}" ]]; then
  echo "No JSON files found in ${JSON_DIR}"
  exit 0
fi

echo "Processing: ${latest_json}"

"$PYTHON_BIN" "$IMPORT_SCRIPT" "$JSON_DIR/$latest_json"

archived_name="${latest_json}.archive"
mv -- "$latest_json" "$archived_name"

echo "Archived: ${archived_name}"