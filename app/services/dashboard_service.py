from app.db.database import get_db_connection


def get_dashboard_stats(user_name: str):
    conn = get_db_connection()

    today_sql = """
        SELECT COALESCE(SUM(daily_kcal), 0) AS kcal_today
        FROM daily_meal
        WHERE user_name = ?
          AND entry_date = date('now')
    """

    week_sql = """
        SELECT COALESCE(ROUND(AVG(daily_kcal), 1), 0) AS kcal_avg_7d
        FROM daily_meal
        WHERE user_name = ?
          AND entry_date >= date('now', '-6 days')
    """

    month_sql = """
        SELECT COALESCE(ROUND(AVG(daily_kcal), 1), 0) AS kcal_avg_30d
        FROM daily_meal
        WHERE user_name = ?
          AND entry_date >= date('now', '-29 days')
    """

    global_sql = """
        SELECT COALESCE(ROUND(AVG(daily_kcal), 1), 0) AS kcal_avg_all
        FROM daily_meal
        WHERE user_name = ?
    """

    weight_sql = """
        SELECT weight_kg, body_fat_pct, muscle_mass_pct, entry_date
        FROM body_metrics
        WHERE user_name = ?
        ORDER BY entry_date DESC
        LIMIT 1
    """

    today = conn.execute(today_sql, (user_name,)).fetchone()
    week = conn.execute(week_sql, (user_name,)).fetchone()
    month = conn.execute(month_sql, (user_name,)).fetchone()
    overall = conn.execute(global_sql, (user_name,)).fetchone()
    latest_weight = conn.execute(weight_sql, (user_name,)).fetchone()

    conn.close()

    return {
        "kcal_today": today["kcal_today"],
        "kcal_avg_7d": week["kcal_avg_7d"],
        "kcal_avg_30d": month["kcal_avg_30d"],
        "kcal_avg_all": overall["kcal_avg_all"],
        "latest_weight": latest_weight,
    }