import json
import sqlite3
import sys
from pathlib import Path

from rapidfuzz import fuzz, process

DB_PATH = "/home/droque/.hermes/data/db/food_diary.db"
UNKNOWN_FOOD_ID = 1
ALLOWED_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snacks"}
FUZZY_SCORE_CUTOFF = 90

def load_json(json_path: str) -> dict:
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except UnicodeDecodeError:
        # Se falhar, assume que o ficheiro está em ISO-8859-1 (Latin-1)
        with path.open("r", encoding="latin-1") as f:
            return json.load(f)

def validate_payload(data: dict) -> None:
    required = ["date", "status", "user", "meals"]
    for field in required:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")

    if data["status"] not in {"partial", "complete", "processed"}:
        raise ValueError("status must be one of: partial, complete, processed")

    if not isinstance(data["meals"], dict):
        raise ValueError("meals must be an object")

def extract_daily_kcal(data: dict) -> float | None:
    totals = data.get("totals") or {}
    daily_kcal = totals.get("daily_kcal")
    return float(daily_kcal) if daily_kcal is not None else None

def extract_notes(data: dict) -> str | None:
    notes = data.get("notes")
    if not notes:
        return None
    if isinstance(notes, list):
        return "\n".join(str(x) for x in notes)
    return str(notes)

def parse_quantity_and_unit(item: dict) -> tuple[float | None, str | None]:
    return item.get("quantity"), item.get("unit")

def ensure_unknown_food_exists(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT id FROM food_master WHERE id = ?",
        (UNKNOWN_FOOD_ID,)
    ).fetchone()
    if not row:
        raise ValueError(f"food_master is missing fallback id={UNKNOWN_FOOD_ID}")

def load_food_master(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT id, food_name, search_text
        FROM food_master
        WHERE search_text IS NOT NULL
          AND TRIM(search_text) <> ''
        """
    ).fetchall()

    foods = []
    for row in rows:
        foods.append({
            "id": row["id"],
            "food_name": row["food_name"],
            "search_text": row["search_text"],
        })
    return foods

def build_food_indexes(food_rows: list[dict]):
    exact_map = {}
    search_choices = []
    choice_to_food = {}

    for food in food_rows:
        search_text = food["search_text"]
        exact_map[search_text] = food["id"]
        search_choices.append(search_text)
        choice_to_food[search_text] = food

    return exact_map, search_choices, choice_to_food

def resolve_food_id(item: dict, exact_map: dict, search_choices: list, choice_to_food: dict) -> tuple[int, str | None, float | None, str]:
    """
    Resolution priority:
    1. explicit item['id']
    2. exact match on description == search_text
    3. fuzzy match on description against search_text
    4. fallback to UNKNOWN_FOOD_ID

    Returns:
        (food_id, matched_food_name, match_score, match_method)
    """
    explicit_id = item.get("id")
    if explicit_id is not None:
        return int(explicit_id), None, None, "explicit_id"

    description = (item.get("description") or "").strip()
    if not description:
        return UNKNOWN_FOOD_ID, None, None, "unknown"

    if description in exact_map:
        matched_food = choice_to_food[description]
        return matched_food["id"], matched_food["food_name"], 100.0, "exact"

    match = process.extractOne(
        description,
        search_choices,
        scorer=fuzz.WRatio,
        score_cutoff=FUZZY_SCORE_CUTOFF
    )

    if match:
        matched_search_text, score, _ = match
        matched_food = choice_to_food[matched_search_text]
        return matched_food["id"], matched_food["food_name"], float(score), "fuzzy"

    return UNKNOWN_FOOD_ID, None, None, "unknown"

def insert_daily_meal(conn: sqlite3.Connection, data: dict) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO daily_meal (
            entry_date,
            meal_status,
            user_name,
            daily_kcal,
            notes
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            data["date"],
            data["status"],
            data["user"],
            extract_daily_kcal(data),
            extract_notes(data)
        )
    )
    return cur.lastrowid

def build_detail_rows(data: dict, exact_map: dict, search_choices: list, choice_to_food: dict):
    rows = []

    for meal_type, items in data["meals"].items():
        if meal_type not in ALLOWED_MEAL_TYPES:
            continue

        for item in items:
            food_id, matched_food_name, match_score, match_method = resolve_food_id(
                item, exact_map, search_choices, choice_to_food
            )
            quantity, unit = parse_quantity_and_unit(item)

            rows.append({
                "meal_type": meal_type,
                "food_id": food_id,
                "quantity": quantity,
                "unit": unit,
                "calories": item.get("kcal"),
                "protein": item.get("protein"),
                "carbs": item.get("carbs"),
                "fat": item.get("fat"),
                "description": item.get("description"),
                "matched_food_name": matched_food_name,
                "match_score": match_score,
                "match_method": match_method,
            })

    return rows

def insert_daily_meal_details(conn: sqlite3.Connection, daily_meal_id: int, detail_rows: list[dict]) -> int:
    if not detail_rows:
        return 0

    payload = [
        (
            daily_meal_id,
            row["meal_type"],
            row["food_id"],
            row["quantity"],
            row["unit"],
            row["calories"],
            row["protein"],
            row["carbs"],
            row["fat"],
        )
        for row in detail_rows
    ]

    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO daily_meal_detail (
            daily_meal_id,
            meal_type,
            food_id,
            quantity,
            unit,
            calories,
            protein,
            carbs,
            fat
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        payload
    )
    return len(payload)

def main():
    if len(sys.argv) != 2:
        print("Usage: python import_meals.py <json_file>")
        sys.exit(1)

    json_file = sys.argv[1]
    data = load_json(json_file)
    validate_payload(data)

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        ensure_unknown_food_exists(conn)

        food_rows = load_food_master(conn)
        exact_map, search_choices, choice_to_food = build_food_indexes(food_rows)

        daily_meal_id = insert_daily_meal(conn, data)
        detail_rows = build_detail_rows(data, exact_map, search_choices, choice_to_food)
        inserted_count = insert_daily_meal_details(conn, daily_meal_id, detail_rows)

        conn.commit()

        print(f"Imported '{json_file}' -> daily_meal_id={daily_meal_id}, detail_rows={inserted_count}")
        for row in detail_rows:
            print({
                "description": row["description"],
                "food_id": row["food_id"],
                "match_method": row["match_method"],
                "matched_food_name": row["matched_food_name"],
                "match_score": row["match_score"],
            })

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()