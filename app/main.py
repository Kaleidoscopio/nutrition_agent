from typing import Optional
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from datetime import date
from app.core.templates import templates
from app.core.config import settings
from app.routers import auth, dashboard
from app.db.database import get_db_connection

#   Constants
MEAL_TYPES = {"breakfast", "lunch", "dinner", "snacks"}
AUTO_CALC_UNITS = {"g", "gram", "grams", "ml"}

app = FastAPI(title=settings.app_name)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie="food_diary_session",
    max_age=60 * 60 * 24 * 30,   # 30 days
    same_site="lax",
    https_only=False,            # True only when serving over HTTPS
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)

#
#   Normalization function for food text
#
def normalize_food_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())

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


def get_current_user_name(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user.get("user_name") or user.get("username") or user.get("name")

#
#   Diary page route
#
@app.get("/diary", response_class=HTMLResponse)
async def food_diary(request: Request, entry_date: str = None):
    user_name = get_current_user_name(request)
    entry_date = entry_date or date.today().isoformat()

    conn = get_db_connection()
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
            fm.food_name
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

    items = []
    for row in rows:
        items.append({
            "id": row["id"],
            "meal_type": row["meal_type"],
            "food_id": row["food_id"],
            "food_label": row["food_label"],
            "food_name": row["food_name"],
            "quantity": row["quantity"],
            "unit": row["unit"],
            "calories": row["calories"],
            "protein": row["protein"],
            "carbs": row["carbs"],
            "fat": row["fat"],
        })

    conn.close()

    return templates.TemplateResponse(
        request,
        "diary.html",
        {
            "user": request.session.get("user"),
            "entry_date": entry_date,
            "daily_meal": dict(daily_meal),
            "items": items,
            "last_meal_type": request.session.get("last_meal_type", "breakfast"),
        },
    )

#
# Route to add a new diary item
#
@app.post("/diary/add")
async def add_diary_item(
    request: Request,
    entry_date: str = Form(...),
    meal_type: str = Form(...),
    food_text: str = Form(...),
    quantity: Optional[float] = Form(None),
    unit: Optional[str] = Form(None),
    manual_calories: Optional[float] = Form(None),
):
    user_name = get_current_user_name(request)

    meal_type = (meal_type or "").strip().lower()
    if meal_type not in MEAL_TYPES:
        raise HTTPException(status_code=400, detail="Invalid meal type")

    typed_food = (food_text or "").strip()
    if not typed_food:
        raise HTTPException(status_code=400, detail="Food is required")

    conn = get_db_connection()
    daily_meal = get_or_create_daily_meal(conn, user_name, entry_date)

    matched_food = match_food(conn, typed_food)

    food_id = matched_food["id"] if matched_food else 1
    nutrition = calculate_nutrition(matched_food, quantity, unit)

    if nutrition:
        calories = nutrition["calories"]
        protein = nutrition["protein"]
        carbs = nutrition["carbs"]
        fat = nutrition["fat"]
    else:
        calories = manual_calories
        protein = None
        carbs = None
        fat = None

    if calories is None:
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
                fm.food_name
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

        response = templates.TemplateResponse(
            request,
            "diary.html",
            {
                "user": request.session.get("user"),
                "entry_date": entry_date,
                "daily_meal": dict(daily_meal),
                "items": items,
                "error_message": "Food not matched automatically. Please enter calories manually.",
                "form_data": {
                    "meal_type": meal_type,
                    "food_text": typed_food,
                    "quantity": quantity,
                    "unit": unit,
                    "manual_calories": manual_calories,
                },
            },
            status_code=400,
        )
        conn.close()
        return response

    conn.execute(
        """
        INSERT INTO daily_meal_detail (
            daily_meal_id,
            meal_type,
            food_id,
            food_label,
            quantity,
            unit,
            calories,
            protein,
            carbs,
            fat
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            daily_meal["id"],
            meal_type,
            food_id,
            typed_food,
            quantity,
            unit.strip().lower() if unit else None,
            calories,
            protein,
            carbs,
            fat,
        ),
    )

    conn.commit()
    recalculate_daily_meal_total(conn, daily_meal["id"])
    conn.close()

    request.session["last_meal_type"] = meal_type

    return RedirectResponse(url=f"/diary?entry_date={entry_date}", status_code=303)

#
# Route to delete a diary item
#
@app.post("/diary/delete/{detail_id}")
async def delete_diary_item(request: Request, detail_id: int):
    user_name = get_current_user_name(request)
    conn = get_db_connection()

    row = conn.execute(
        """
        SELECT dmd.id, dmd.daily_meal_id, dm.entry_date, dm.user_name
        FROM daily_meal_detail dmd
        JOIN daily_meal dm ON dm.id = dmd.daily_meal_id
        WHERE dmd.id = ?
        """,
        (detail_id,),
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Meal item not found")

    if row["user_name"] != user_name:
        conn.close()
        raise HTTPException(status_code=403, detail="Forbidden")

    conn.execute("DELETE FROM daily_meal_detail WHERE id = ?", (detail_id,))
    conn.commit()
    recalculate_daily_meal_total(conn, row["daily_meal_id"])
    entry_date = row["entry_date"]
    conn.close()

    return RedirectResponse(url=f"/diary?entry_date={entry_date}", status_code=303)

#
# Route to update a diary item
#
@app.post("/diary/update/{detail_id}")
async def update_diary_item(
    request: Request,
    detail_id: int,
    meal_type: str = Form(...),
    food_text: str = Form(...),
    quantity: Optional[float] = Form(None),
    unit: Optional[str] = Form(None),
    manual_calories: Optional[float] = Form(None),
):
    user_name = get_current_user_name(request)

    meal_type = (meal_type or "").strip().lower()
    if meal_type not in MEAL_TYPES:
        raise HTTPException(status_code=400, detail="Invalid meal type")

    typed_food = (food_text or "").strip()
    if not typed_food:
        raise HTTPException(status_code=400, detail="Food is required")

    conn = get_db_connection()

    existing = conn.execute(
        """
        SELECT dmd.id, dmd.daily_meal_id, dm.entry_date, dm.user_name
        FROM daily_meal_detail dmd
        JOIN daily_meal dm ON dm.id = dmd.daily_meal_id
        WHERE dmd.id = ?
        """,
        (detail_id,),
    ).fetchone()

    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Meal item not found")

    if existing["user_name"] != user_name:
        conn.close()
        raise HTTPException(status_code=403, detail="Forbidden")

    matched_food = match_food(conn, typed_food)
    food_id = matched_food["id"] if matched_food else 1
    nutrition = calculate_nutrition(matched_food, quantity, unit)

    if nutrition:
        calories = nutrition["calories"]
        protein = nutrition["protein"]
        carbs = nutrition["carbs"]
        fat = nutrition["fat"]
    else:
        calories = manual_calories
        protein = None
        carbs = None
        fat = None

    if calories is None:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Calories are required when food is not matched or cannot be auto-calculated",
        )

    conn.execute(
        """
        UPDATE daily_meal_detail
        SET
            meal_type = ?,
            food_id = ?,
            food_label = ?,
            quantity = ?,
            unit = ?,
            calories = ?,
            protein = ?,
            carbs = ?,
            fat = ?
        WHERE id = ?
        """,
        (
            meal_type,
            food_id,
            typed_food,
            quantity,
            unit.strip().lower() if unit else None,
            calories,
            protein,
            carbs,
            fat,
            detail_id,
        ),
    )

    conn.commit()
    recalculate_daily_meal_total(conn, existing["daily_meal_id"])
    entry_date = existing["entry_date"]
    conn.close()

    return RedirectResponse(url=f"/diary?entry_date={entry_date}", status_code=303)