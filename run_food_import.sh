#!/usr/bin/env bash
set -euo pipefail

# Directories
FOOD_DIR="/home/droque/.hermes/data/food-diary/entries"
METRICS_DIR="/home/droque/.hermes/data/body-metrics/entries"

# Scripts & Binaries
PYTHON_BIN="/usr/bin/python3"
MEAL_SCRIPT="/home/droque/.hermes/scripts/import_meals.py"
ACTIVITY_SCRIPT="/home/droque/.hermes/scripts/import_activity.py"

# 1. Process Meals First
if cd "$FOOD_DIR" 2>/dev/null; then
    latest_meal="$(ls -t *.json 2>/dev/null | head -n 1 || true)"
    if [[ -n "${latest_meal}" ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processing Meal Log: $FOOD_DIR/$latest_meal"
        "$PYTHON_BIN" "$MEAL_SCRIPT" "$FOOD_DIR/$latest_meal"
        mv -- "$latest_meal" "${latest_meal}.archive"
        echo "Archived: ${latest_meal}.archive"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] No new meal files found in $FOOD_DIR"
    fi
fi

# 2. Process Activity & Metrics Second
if cd "$METRICS_DIR" 2>/dev/null; then
    latest_activity="$(ls -t *.json 2>/dev/null | head -n 1 || true)"
    if [[ -n "${latest_activity}" ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processing Activity Log: $METRICS_DIR/$latest_activity"
        "$PYTHON_BIN" "$ACTIVITY_SCRIPT" "$METRICS_DIR/$latest_activity"
        mv -- "$latest_activity" "${latest_activity}.archive"
        echo "Archived: ${latest_activity}.archive"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] No new activity files found in $METRICS_DIR"
    fi
fi