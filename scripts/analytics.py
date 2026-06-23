import sqlite3
from datetime import datetime

DB_PATH = "/home/droque/.hermes/data/db/food_diary.db"

def get_average_calories(days: int, user_name: str) -> float:
    """
    Calculates the average calories consumed by a specific user over the last X days.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Using daily_meal table which already contains consolidated daily totals
    query = """
        SELECT AVG(daily_kcal) 
        FROM daily_meal 
        WHERE user_name = ? 
          AND entry_date >= date('now', ?)
    """
    try:
        cursor.execute(query, (user_name, f'-{days} days'))
        result = cursor.fetchone()[0]
        return round(result, 2) if result is not None else 0.0
    except sqlite3.Error as e:
        print(f"Database error in get_average_calories: {e}")
        return 0.0
    finally:
        conn.close()


def predict_weight_change(projection_days: int, user_name: str) -> dict:
    """
    Predicts weight evolution over 10, 30, or 90 days based on the 
    historical deficit trend (TDEE vs Consumed Kcal) from the last 14 days.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Fetch current weight from body_metrics
    weight_query = """
        SELECT weight_kg 
        FROM body_metrics 
        WHERE user_name = ? AND weight_kg IS NOT NULL
        ORDER BY entry_date DESC LIMIT 1
    """
    
    # 2. Fetch the average daily calorie deficit/surplus over the last 14 days
    # Net balance is already tracked inside daily_expenditure (consumed - tdee)
    trend_query = """
        SELECT AVG(net_balance_kcal)
        FROM daily_expenditure
        WHERE user_name = ?
          AND entry_date >= date('now', '-14 days')
    """
    
    try:
        cursor.execute(weight_query, (user_name,))
        weight_row = cursor.fetchone()
        current_weight = weight_row[0] if weight_row else None
        
        cursor.execute(trend_query, (user_name,))
        trend_row = cursor.fetchone()
        avg_net_balance = trend_row[0] if trend_row and trend_row[0] is not None else None
        
        if current_weight is None or avg_net_balance is None:
            return {
                "status": "error",
                "message": "Insufficient historical data in body_metrics or daily_expenditure to calculate trends."
            }
        
        # Thermodynamics: 7700 kcal deficit = ~1kg weight lost
        # If net_balance is negative, user is in a deficit (losing weight)
        # Total projected calorie balance over the period:
        total_projected_kcal = avg_net_balance * projection_days
        weight_change_kg = total_projected_kcal / 7700
        projected_weight = current_weight + weight_change_kg
        
        return {
            "status": "success",
            "user_name": user_name,
            "current_weight_kg": round(current_weight, 2),
            "projected_weight_kg": round(projected_weight, 2),
            "estimated_change_kg": round(weight_change_kg, 2),
            "days_forecasted": projection_days,
            "avg_daily_net_kcal": round(avg_net_balance, 2)
        }
        
    except sqlite3.Error as e:
        return {"status": "error", "message": f"Database error: {str(e)}"}
    finally:
        conn.close()