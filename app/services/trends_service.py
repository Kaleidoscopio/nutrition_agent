from datetime import date, timedelta
from statistics import mean
from app.db.database import get_db_connection
from app.services.metabolism_service import build_energy_summary

PERIOD_TO_DAYS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "180d": 180,
    "365d": 365,
}

#
#   Return the most recent non zero value
#
def latest_non_zero(values):
    for value in reversed(values):
        if value not in (None, 0):
            return value
    return 0

def parse_period(period: str | None) -> str:
    period = (period or "30d").strip().lower()
    return period if period in PERIOD_TO_DAYS else "30d"


def build_projection(latest_weight_kg: float | None, daily_weight_delta: float, days: int) -> str:
    if latest_weight_kg is None:
        return "—"
    projected = latest_weight_kg + (daily_weight_delta * days)
    return f"{projected:.1f} kg"

#
#   Gets the lower and upper limit of the selection (ignoring the current day)
#
def get_period_bounds(period: str):
    days = PERIOD_TO_DAYS[period]
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)
    return start_date.isoformat(), end_date.isoformat()

#
#   Gets the average of a series of values ignoring value at 0 or None
#
def average_ignore_zero(values):
    filtered = [value for value in values if value not in (None, 0)]
    return round(mean(filtered)) if filtered else 0

#
#   Returns a list of values, replacing empty entries with the last recorded value
#
def forward_fill(values):
    filled = []
    last_value = None

    for value in values:
        if value is not None:
            last_value = value
            filled.append(value)
        else:
            filled.append(last_value)

    return filled


def build_trends_payload(conn, user_name: str, period: str):
    start_date, end_date = get_period_bounds(period)
    history_rows = load_trends_history(conn, user_name, start_date, end_date)

    labels = [row["day"] for row in history_rows]
    calories_in = [row["calories_in"] for row in history_rows]
    calories_out = [row["calories_out"] for row in history_rows]
    bmr_kcal = [row["bmr_kcal"] for row in history_rows]
    activity_kcal = [row["activity_kcal"] for row in history_rows]
    tdee_kcal = [row["tdee_kcal"] for row in history_rows]
    net_balance_kcal = [row["net_balance_kcal"] for row in history_rows]

    raw_weights = [row["weight_kg"] for row in history_rows]
    weights = forward_fill(raw_weights)

    body_fat_pct = [row["body_fat_pct"] for row in history_rows]
    muscle_mass_pct = [row["muscle_mass_pct"] for row in history_rows]
    bmi_values = [row["bmi"] for row in history_rows]

    weight_points = [value for value in raw_weights if value is not None]
    latest_weight_kg = weight_points[-1] if weight_points else None

    if len(weight_points) >= 2:
        total_weight_delta = weight_points[-1] - weight_points[0]
        daily_weight_delta = total_weight_delta / max(len(weight_points) - 1, 1)
        weight_delta = f"{total_weight_delta:+.1f} kg"
    else:
        daily_weight_delta = 0.0
        weight_delta = "—"

    latest_metrics_row = None
    for row in reversed(history_rows):
        if (
            row["weight_kg"] is not None
            or row["body_fat_pct"] is not None
            or row["muscle_mass_pct"] is not None
            or row["bmi"] is not None
        ):
            latest_metrics_row = row
            break

    avg_calories_in = average_ignore_zero(calories_in)
    avg_calories_out = average_ignore_zero(calories_out)
    avg_bmr_kcal = average_ignore_zero(bmr_kcal)
    avg_activity_kcal = average_ignore_zero(activity_kcal)
    avg_tdee_kcal = average_ignore_zero(tdee_kcal)
    avg_net_balance_kcal = average_ignore_zero(net_balance_kcal)

    latest_net_balance = latest_non_zero(net_balance_kcal)
    latest_tdee = latest_non_zero(tdee_kcal)

    today_sql = """
        SELECT COALESCE(SUM(daily_kcal), 0) AS kcal_today
        FROM daily_meal
        WHERE user_name = ?
          AND entry_date = date('now')
    """

    profile_sql = """
        SELECT sex, date_of_birth, height_cm, start_weight_kg, activity_level, display_name, email
        FROM users
        WHERE user_name = ?
        LIMIT 1
    """
	
    #   Get Estimated Maintenance Value
    today = conn.execute(today_sql, (user_name,)).fetchone()
    profile = conn.execute(profile_sql, (user_name,)).fetchone()

    profile_data = dict(profile) if profile else {}
    if latest_weight_kg is not None:
        profile_data["weight_kg"] = latest_weight_kg

    estimated_maintenance_kcal = build_energy_summary(profile_data, today["kcal_today"]).get("tdee", 0)
	
    return {
        "selected_period": period,
        "history_rows": history_rows,

        "avg_calories_in": avg_calories_in,
        "avg_calories_out": avg_calories_out,
        "avg_bmr_kcal": avg_bmr_kcal,
        "avg_activity_kcal": avg_activity_kcal,
        "avg_tdee_kcal": avg_tdee_kcal,
        "avg_net_balance_kcal": avg_net_balance_kcal,

        "latest_net_balance_kcal": latest_net_balance,
        "latest_tdee_kcal": latest_tdee,

        "weight_delta": weight_delta,
        "latest_weight": f"{latest_weight_kg:.1f} kg" if latest_weight_kg is not None else "—",
        "latest_body_fat": (
            f'{latest_metrics_row["body_fat_pct"]:.1f}%'
            if latest_metrics_row and latest_metrics_row["body_fat_pct"] is not None
            else None
        ),
        "latest_muscle_mass": (
            f'{latest_metrics_row["muscle_mass_pct"]:.1f}%'
            if latest_metrics_row and latest_metrics_row["muscle_mass_pct"] is not None
            else None
        ),
        "latest_bmi": (
            f'{latest_metrics_row["bmi"]:.1f}'
            if latest_metrics_row and latest_metrics_row["bmi"] is not None
            else None
        ),

        "projection_30d": build_projection(latest_weight_kg, daily_weight_delta, 30),
        "projection_90d": build_projection(latest_weight_kg, daily_weight_delta, 90),
        "projection_180d": build_projection(latest_weight_kg, daily_weight_delta, 180),
        "projection_365d": build_projection(latest_weight_kg, daily_weight_delta, 365),

        "chart_data": {
            "labels": labels,
            "calories_in": calories_in,
            "calories_out": calories_out,
            "bmr_kcal": bmr_kcal,
            "activity_kcal": activity_kcal,
            "tdee_kcal": tdee_kcal,
            "net_balance_kcal": net_balance_kcal,
            "weights": weights,
            "body_fat_pct": body_fat_pct,
            "muscle_mass_pct": muscle_mass_pct,
            "bmi": bmi_values,
            "maintenance_kcal": [estimated_maintenance_kcal] * len(labels) if estimated_maintenance_kcal else [],
        },
    }


def load_trends_history(conn, user_name: str, start_date: str, end_date: str):
    rows = conn.execute(
        """
        WITH RECURSIVE dates(day) AS (
            SELECT ?
            UNION ALL
            SELECT date(day, '+1 day')
            FROM dates
            WHERE day < ?
        ),
        intake AS (
            SELECT
                dm.entry_date AS day,
                ROUND(COALESCE(SUM(dmd.calories), 0), 0) AS calories_in
            FROM daily_meal dm
            LEFT JOIN daily_meal_detail dmd
                ON dmd.daily_meal_id = dm.id
            WHERE dm.user_name = ?
              AND dm.entry_date BETWEEN ? AND ?
            GROUP BY dm.entry_date
        ),
        activity AS (
            SELECT
                de.entry_date AS day,
                COALESCE(de.bmr_kcal, 0) AS bmr_kcal,
                COALESCE(de.activity_kcal, 0) AS activity_kcal,
                COALESCE(de.tdee_kcal, 0) AS tdee_kcal,
                COALESCE(de.net_balance_kcal, 0) AS net_balance_kcal,
                ROUND(COALESCE(SUM(la.calories_burned), 0), 0) AS logged_activity_kcal
            FROM daily_expenditure de
            LEFT JOIN log_activities la
                ON la.expenditure_id = de.id
            WHERE de.user_name = ?
              AND de.entry_date BETWEEN ? AND ?
            GROUP BY
                de.entry_date,
                de.bmr_kcal,
                de.activity_kcal,
                de.tdee_kcal,
                de.net_balance_kcal
        ),
        metrics AS (
            SELECT
                bm.entry_date AS day,
                bm.weight_kg,
                bm.body_fat_pct,
                bm.muscle_mass_pct,
                bm.bmi
            FROM body_metrics bm
            WHERE bm.user_name = ?
              AND bm.entry_date BETWEEN ? AND ?
        )
        SELECT
            d.day,
            COALESCE(i.calories_in, 0) AS calories_in,
            COALESCE(a.logged_activity_kcal, 0) AS calories_out,
            COALESCE(a.bmr_kcal, 0) AS bmr_kcal,
            COALESCE(a.activity_kcal, 0) AS activity_kcal,
            COALESCE(a.tdee_kcal, 0) AS tdee_kcal,
            COALESCE(a.net_balance_kcal, 0) AS net_balance_kcal,
            m.weight_kg,
            m.body_fat_pct,
            m.muscle_mass_pct,
            m.bmi
        FROM dates d
        LEFT JOIN intake i ON i.day = d.day
        LEFT JOIN activity a ON a.day = d.day
        LEFT JOIN metrics m ON m.day = d.day
        ORDER BY d.day ASC
        """,
        (
            start_date,
            end_date,
            user_name, start_date, end_date,
            user_name, start_date, end_date,
            user_name, start_date, end_date,
        ),
    ).fetchall()

    history_rows = []
    for row in rows:
        history_rows.append({
            "day": row["day"],
            "calories_in": row["calories_in"] or 0,
            "calories_out": row["calories_out"] or 0,
            "bmr_kcal": row["bmr_kcal"] or 0,
            "activity_kcal": row["activity_kcal"] or 0,
            "tdee_kcal": row["tdee_kcal"] or 0,
            "net_balance_kcal": row["net_balance_kcal"] or 0,
            "weight_kg": row["weight_kg"],
            "body_fat_pct": row["body_fat_pct"],
            "muscle_mass_pct": row["muscle_mass_pct"],
            "bmi": row["bmi"],
        })

    return history_rows