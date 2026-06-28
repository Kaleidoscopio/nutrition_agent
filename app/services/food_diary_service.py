from fastapi import Request
from app.core.templates import templates

#   Constants
AUTO_CALC_UNITS = {"g", "gram", "grams", "ml"}

#
#   Auxiliary Functions for food_diary.py
#
def get_or_create_daily_meal(conn, user_name: str, entry_date: str):
    row = conn.execute(
        """
        SELECT id, entry_date, meal_status, user_name, daily_kcal, notes
        FROM daily_meal
        WHERE entry_date = ? AND user_name = ?
        """,
        (entry_date, user_name),
    ).fetchone()

    if row:
        return row

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO daily_meal (entry_date, meal_status, user_name, daily_kcal, notes)
        VALUES (?, 'partial', ?, 0, NULL)
        """,
        (entry_date, user_name),
    )
    conn.commit()

    return conn.execute(
        """
        SELECT id, entry_date, meal_status, user_name, daily_kcal, notes
        FROM daily_meal
        WHERE id = ?
        """,
        (cur.lastrowid,),
    ).fetchone()

#
def calculate_nutrition(food_row, quantity: float, unit: str):
    if not food_row or quantity is None or quantity <= 0:
        return None

    unit_normalized = (unit or "").strip().lower()
    if unit_normalized not in AUTO_CALC_UNITS:
        return None

    calories_100g = food_row["calories_100g"]
    protein_100g = food_row["protein_100g"]
    carbs_100g = food_row["carbs_100g"]
    fat_100g = food_row["fat_100g"]

    if calories_100g is None:
        return None

    factor = quantity / 100.0

    return {
        "calories": round((calories_100g or 0) * factor, 2),
        "protein": round((protein_100g or 0) * factor, 2) if protein_100g is not None else None,
        "carbs": round((carbs_100g or 0) * factor, 2) if carbs_100g is not None else None,
        "fat": round((fat_100g or 0) * factor, 2) if fat_100g is not None else None,
    }

#
#   Normalization function for food text
#
def normalize_food_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())

#
#   Match food name on Database
#
def match_food(conn, typed_food: str):
    normalized = normalize_food_text(typed_food)
    if not normalized:
        return None

    #   Search for an exact match
    exact_master = conn.execute(
        """
        SELECT id, food_name, search_text, calories_100g, protein_100g, carbs_100g, fat_100g
        FROM food_master
        WHERE search_text = ?
        LIMIT 1
        """,
        (normalized,),
    ).fetchone()

    if exact_master:
        return exact_master

    #   Search for an exact alias
    exact_alias = conn.execute(
        """
        SELECT fm.id, fm.food_name, fm.search_text, fm.calories_100g, fm.protein_100g, fm.carbs_100g, fm.fat_100g
        FROM food_alias fa
        JOIN food_master fm ON fm.id = fa.food_id
        WHERE lower(trim(fa.alias)) = ?
        LIMIT 1
        """,
        (normalized,),
    ).fetchone()
    if exact_alias:
        return exact_alias
    
    like_term = f"%{normalized}%"

    #   Search for a partial match
    partial_master = conn.execute(
        """
        SELECT id, food_name, search_text, calories_100g, protein_100g, carbs_100g, fat_100g
        FROM food_master
        WHERE search_text LIKE ?
        ORDER BY LENGTH(search_text) ASC
        LIMIT 1
        """,
        (like_term,),
    ).fetchone()
    if partial_master:
        return partial_master

    #   Search for a partial alias
    partial_alias = conn.execute(
        """
        SELECT fm.id, fm.food_name, fm.search_text, fm.calories_100g, fm.protein_100g, fm.carbs_100g, fm.fat_100g
        FROM food_alias fa
        JOIN food_master fm ON fm.id = fa.food_id
        WHERE lower(trim(fa.alias)) LIKE ?
        ORDER BY LENGTH(fa.alias) ASC
        LIMIT 1
        """,
        (like_term,),
    ).fetchone()
    if partial_alias:
        return partial_alias

    return None

#
#   Sum up calories for the day
#
def recalculate_daily_meal_total(conn, daily_meal_id: int):
    total = conn.execute(
        """
        SELECT COALESCE(SUM(calories), 0)
        FROM daily_meal_detail
        WHERE daily_meal_id = ?
        """,
        (daily_meal_id,),
    ).fetchone()[0]

    conn.execute(
        """
        UPDATE daily_meal
        SET daily_kcal = ?
        WHERE id = ?
        """,
        (round(total or 0), daily_meal_id),
    )
    conn.commit()

#
#   Search for all possible food matches
#
def search_food_matches(conn, typed_food: str):
    search = normalize_food_text(typed_food)
    if not search:
        return []

    like = f"%{search}%"

    rows = conn.execute(
        """
        SELECT DISTINCT
            x.id,
            x.food_name,
            x.food_category,
            x.calories_100g,
            x.protein_100g,
            x.carbs_100g,
            x.fat_100g
        FROM (
            SELECT
                fm.id,
                fm.food_name,
                fm.food_category,
                fm.calories_100g,
                fm.protein_100g,
                fm.carbs_100g,
                fm.fat_100g
            FROM food_master fm
            WHERE lower(fm.food_name) LIKE ?
               OR lower(coalesce(fm.search_text, '')) LIKE ?

            UNION

            SELECT
                fm.id,
                fm.food_name,
                fm.food_category,
                fm.calories_100g,
                fm.protein_100g,
                fm.carbs_100g,
                fm.fat_100g
            FROM food_alias fa
            JOIN food_master fm ON fm.id = fa.food_id
            WHERE lower(fa.alias) LIKE ?
        ) AS x
        ORDER BY
            CASE
                WHEN lower(x.food_name) = ? THEN 1
                WHEN lower(x.food_name) LIKE ? THEN 2
                ELSE 3
            END,
            x.food_category,
            x.food_name
        LIMIT 20
        """,
        (like, like, like, search, f"{search}%"),
    ).fetchall()

    return [dict(row) for row in rows]

#
#   Get food item by id
#
def get_food_by_id(conn, food_id: int):
    row = conn.execute(
        """
        SELECT
            id,
            food_name,
            food_category,
            calories_100g,
            protein_100g,
            carbs_100g,
            fat_100g
        FROM food_master
        WHERE id = ?
        LIMIT 1
        """,
        (food_id,),
    ).fetchone()

    return dict(row) if row else None

#
#   Build food match candidates
#
def build_match_context(candidates):
    categories = []
    seen = set()

    for candidate in candidates:
        category = candidate.get("food_category") or "Uncategorized"
        if category not in seen:
            seen.add(category)
            categories.append(category)

    return {
        "match_candidates": candidates,
        "match_categories": categories,
        "show_match_modal": len(candidates) > 1,
    }

#
#   Render the Diary Page
#
def render_diary_page(
    request: Request,
    conn,
    user_name: str,
    entry_date: str,
    error: str | None = None,
    success: str | None = None,
    form_data: dict | None = None,
    match_candidates: list | None = None,
    status_code: int = 200,
):
    daily_meal = get_or_create_daily_meal(conn, user_name, entry_date)

    rows = conn.execute(
        """
        SELECT
            dmd.id,
            dmd.meal_type,
            dmd.food_id,
            dmd.food_label,
            dmd.quantity,
            dmd.unit,
            dmd.calories,
            dmd.protein,
            dmd.carbs,
            dmd.fat,
            fm.food_name,
            fm.food_category
        FROM daily_meal_detail dmd
        LEFT JOIN food_master fm ON fm.id = dmd.food_id
        WHERE dmd.daily_meal_id = ?
        ORDER BY
            CASE dmd.meal_type
                WHEN 'breakfast' THEN 1
                WHEN 'lunch' THEN 2
                WHEN 'dinner' THEN 3
                WHEN 'snacks' THEN 4
                ELSE 5
            END,
            dmd.id ASC
        """,
        (daily_meal["id"],),
    ).fetchall()

    items = [dict(row) for row in rows]

    context = {
        "request": request,
        "user": request.session.get("user"),
        "entry_date": entry_date,
        "daily_meal": dict(daily_meal),
        "items": items,
        "error": error,
        "success": success,
        "form_data": form_data or {},
        "last_meal_type": request.session.get("last_meal_type", "breakfast"),
        "match_candidates": match_candidates or [],
        "match_categories": [],
        "show_match_modal": False,
    }

    if match_candidates:
        context.update(build_match_context(match_candidates))

    return templates.TemplateResponse(request, "diary.html", context, status_code=status_code)