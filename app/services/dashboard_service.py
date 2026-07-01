from app.db.database import get_db_connection
from app.services.metabolism_service import build_energy_summary


def get_dashboard_stats(user_name: str):
    conn = get_db_connection()

    today_sql = """
        SELECT COALESCE(SUM(daily_kcal), 0) AS kcal_today
        FROM daily_meal
        WHERE user_name = ?
          AND entry_date = CURRENT_DATE
    """

    week_sql = """
        SELECT COALESCE(ROUND(AVG(daily_kcal), 1), 0) AS kcal_avg_7d
        FROM daily_meal
        WHERE user_name = ?
          AND entry_date >= (CURRENT_DATE - 6)
    """

    month_sql = """
        SELECT COALESCE(ROUND(AVG(daily_kcal), 1), 0) AS kcal_avg_30d
        FROM daily_meal
        WHERE user_name = ?
          AND entry_date >= (CURRENT_DATE - 29)
    """

    global_sql = """
        SELECT COALESCE(ROUND(AVG(daily_kcal), 1), 0) AS kcal_avg_all
        FROM daily_meal
        WHERE user_name = ?
    """

    #   Gets most recent Weight, Fat % and Muscle %. 
    #   If Fat % or Muscle % are null, looks for the most recent non null value.
    weight_sql = """
        SELECT
            bm.id,
            bm.weight_kg,
            COALESCE(
                bm.body_fat_pct,
                (
                    SELECT prev.body_fat_pct
                    FROM body_metrics AS prev
                    WHERE prev.user_name = bm.user_name
                    AND prev.body_fat_pct IS NOT NULL
                    AND (
                        prev.entry_date < bm.entry_date
                        OR (prev.entry_date = bm.entry_date AND prev.id < bm.id)
                    )
                    ORDER BY prev.entry_date DESC, prev.id DESC
                    LIMIT 1
                )
            ) AS body_fat_pct,
            COALESCE(
                bm.muscle_mass_pct,
                (
                    SELECT prev.muscle_mass_pct
                    FROM body_metrics AS prev
                    WHERE prev.user_name = bm.user_name
                    AND prev.muscle_mass_pct IS NOT NULL
                    AND (
                        prev.entry_date < bm.entry_date
                        OR (prev.entry_date = bm.entry_date AND prev.id < bm.id)
                    )
                    ORDER BY prev.entry_date DESC, prev.id DESC
                    LIMIT 1
                )
            ) AS muscle_mass_pct,
            bm.bmi,
            bm.entry_date
        FROM body_metrics AS bm
        WHERE bm.user_name = ?
        ORDER BY bm.entry_date DESC, bm.id DESC
        LIMIT 1
    """

    profile_sql = """
        SELECT sex, date_of_birth, height_cm, start_weight_kg, activity_level, display_name, email
        FROM users
        WHERE user_name = ?
        LIMIT 1
    """

    today = conn.execute(today_sql, (user_name,)).fetchone()
    week = conn.execute(week_sql, (user_name,)).fetchone()
    month = conn.execute(month_sql, (user_name,)).fetchone()
    overall = conn.execute(global_sql, (user_name,)).fetchone()
    latest_weight = conn.execute(weight_sql, (user_name,)).fetchone()
    profile = conn.execute(profile_sql, (user_name,)).fetchone()

    conn.close()

    profile_data = dict(profile) if profile else {}
    if latest_weight and latest_weight["weight_kg"]:
        profile_data["weight_kg"] = latest_weight["weight_kg"]

    energy = build_energy_summary(profile_data, today["kcal_today"])

    return {
        "kcal_today": today["kcal_today"],
        "kcal_avg_7d": week["kcal_avg_7d"],
        "kcal_avg_30d": month["kcal_avg_30d"],
        "kcal_avg_all": overall["kcal_avg_all"],
        "latest_weight": latest_weight,
        "energy": energy,
    }