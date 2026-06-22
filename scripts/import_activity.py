import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = "/home/droque/.hermes/data/db/food_diary.db"

def load_json(json_path: str) -> dict:
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def validate_activity_payload(data: dict) -> None:
    required = ["date", "status", "user"]
    for field in required:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")

    if data["status"] not in {"partial", "complete", "processed"}:
        raise ValueError("status must be one of: partial, complete, processed")

    if "activity" not in data and "measurements" not in data:
        raise ValueError("Payload missing 'activity' or 'measurements' blocks.")

def get_consumed_calories(conn: sqlite3.Connection, entry_date: str, user_name: str) -> int:
    """Queries the daily_meal table populated by the previous script execution."""
    row = conn.execute(
        """
        SELECT daily_kcal 
        FROM daily_meal 
        WHERE entry_date = ? AND user_name = ?
        """,
        (entry_date, user_name)
    ).fetchone()
    
    if row and row[0] is not None:
        return int(row[0])
    return 0

def upsert_expenditure_summary(conn: sqlite3.Connection, data: dict, consumed_kcal: int) -> int:
    cur = conn.cursor()
    date = data["date"]
    user = data["user"]
    status = data["status"]
    
    estimates = data.get("estimates") or {}
    activity_kcal = estimates.get("activity_kcal") or 0
    tdee_kcal = estimates.get("tdee_kcal") or 0
    
    # Calculate net balance using the retrieved daily_meal calories
    net_balance_kcal = estimates.get("net_balance_kcal")
    if net_balance_kcal is None and tdee_kcal > 0:
        net_balance_kcal = consumed_kcal - tdee_kcal

    notes_list = data.get("notes") or []
    notes_str = "\n".join(notes_list) if isinstance(notes_list, list) else str(notes_list)

    cur.execute(
        """
        INSERT INTO daily_expenditure (
            entry_date, user_name, status, activity_kcal, tdee_kcal, net_balance_kcal, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(entry_date, user_name) DO UPDATE SET
            status = excluded.status,
            activity_kcal = excluded.activity_kcal,
            tdee_kcal = excluded.tdee_kcal,
            net_balance_kcal = excluded.net_balance_kcal,
            notes = excluded.notes
        """,
        (date, user, status, activity_kcal, tdee_kcal, net_balance_kcal, notes_str)
    )
    
    # Return the autoincremented ID for foreign key usage
    row = cur.execute(
        "SELECT id FROM daily_expenditure WHERE entry_date = ? AND user_name = ?", 
        (date, user)
    ).fetchone()
    return row[0]

def process_log_activities(conn: sqlite3.Connection, expenditure_id: int, activity_block: dict) -> int:
    cur = conn.cursor()
    activity_rows = []
    
    if not activity_block:
        return 0

    if activity_block.get("steps") is not None:
        activity_rows.append((expenditure_id, "steps", None, str(activity_block["steps"])))
    
    if activity_block.get("strength_training_minutes") is not None:
        # Robust handling for null, missing, or list structures
        raw_other = activity_block.get("other_activity")
        if isinstance(raw_other, list):
            other_desc = ", ".join(str(x) for x in raw_other)
        elif isinstance(raw_other, str):
            other_desc = raw_other
        else:
            other_desc = ""
            
        final_desc = other_desc if other_desc.strip() else "strength"
        activity_rows.append((expenditure_id, "strength", activity_block["strength_training_minutes"], final_desc))
        
    if activity_block.get("cardio_minutes") is not None:
        activity_rows.append((expenditure_id, "cardio", activity_block["cardio_minutes"], "cardio"))

    # Flush old records for this summary log before inserting fresh values
    cur.execute("DELETE FROM log_activities WHERE expenditure_id = ?", (expenditure_id,))
    
    if activity_rows:
        cur.executemany(
            """
            INSERT INTO log_activities (expenditure_id, activity_type, duration_minutes, activity_value)
            VALUES (?, ?, ?, ?)
            """,
            activity_rows
        )
    return len(activity_rows)

def upsert_body_metrics(conn: sqlite3.Connection, data: dict) -> bool:
    cur = conn.cursor()
    metrics = data.get("measurements") or {}
    
    # Only hit the metrics table if there's actual physical metrics tracking data present
    metric_keys = ["weight_kg", "bmi", "muscle_mass_pct", "body_fat_pct"]
    if not any(metrics.get(k) is not None for k in metric_keys):
        return False

    cur.execute(
        """
        INSERT INTO body_metrics (
            entry_date, user_name, weight_kg, bmi, muscle_mass_pct, body_fat_pct
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(entry_date, user_name) DO UPDATE SET
            weight_kg = COALESCE(excluded.weight_kg, weight_kg),
            bmi = COALESCE(excluded.bmi, bmi),
            muscle_mass_pct = COALESCE(excluded.muscle_mass_pct, muscle_mass_pct),
            body_fat_pct = COALESCE(excluded.body_fat_pct, body_fat_pct)
        """,
        (
            data["date"], data["user"],
            metrics.get("weight_kg"), metrics.get("bmi"),
            metrics.get("muscle_mass_pct"),
            metrics.get("body_fat_pct")
        )
    )
    return True

def main():
    if len(sys.argv) != 2:
        print("Usage: python import_activity.py <json_file>")
        sys.exit(1)

    json_file = sys.argv[1]
    data = load_json(json_file)
    validate_activity_payload(data)

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Cross-reference the database to read what the meal loader script created
        consumed_kcal = get_consumed_calories(conn, data["date"], data["user"])
        
        # Execute relational upserts
        expenditure_id = upsert_expenditure_summary(conn, data, consumed_kcal)
        activity_count = process_log_activities(conn, expenditure_id, data.get("activity", {}))
        metrics_updated = upsert_body_metrics(conn, data)
        
        conn.commit()
        
        print(f"Activity Processing Success [{data['date']} - {data['user']}]:")
        print(f" -> Matched Consumed Calories: {consumed_kcal} kcal")
        print(f" -> Expenditure Table ID: {expenditure_id}")
        print(f" -> Logged Exercise Types: {activity_count}")
        print(f" -> Body Metrics Row Updated: {metrics_updated}")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()