from fastapi import APIRouter, Request, Form
from fastapi import HTTPException
from datetime import date
from typing import Optional
from starlette.responses import RedirectResponse
from app.core.auth import get_current_user_name, login_redirect
from app.core.templates import templates
from app.db.database import get_db_connection
from app.services.food_diary_service import get_or_create_daily_meal, calculate_nutrition, match_food, get_food_by_id
from app.services.food_diary_service import recalculate_daily_meal_total, render_diary_page, search_food_matches

#   Constants
MEAL_TYPES = {"breakfast", "lunch", "dinner", "snacks"}

router = APIRouter()

#
#   Diary page route
#
#@router.get("/diary", response_class=HTMLResponse)
@router.get("/diary")
async def food_diary(request: Request, entry_date: str = None):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    
    user_name = get_current_user_name(request)
    entry_date = entry_date or date.today().isoformat()
    #   Get the session variable (if available)
    success_message = request.session.pop("diary_success", None)

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
            "success": success_message,
            "error": None,
            "form_data": {},
            "last_meal_type": request.session.get("last_meal_type", "breakfast"),
            "match_candidates": [],
            "match_categories": [],
            "show_match_modal": False,
        },
    )

#
# Route to add a new diary item
#
@router.post("/diary/add")
async def add_diary_item(
    request: Request,
    entry_date: str = Form(...),
    meal_type: str = Form(...),
    food_text: str = Form(...),
    quantity: Optional[float] = Form(None),
    unit: Optional[str] = Form(None),
    manual_calories: Optional[float] = Form(None),
    selected_food_id: Optional[str] = Form(None),
    manual_override: Optional[str] = Form(None),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)

    #   Normalize selected_food_id
    selected_food_id_value = None
    if selected_food_id is not None and str(selected_food_id).strip() != "":
        try:
            selected_food_id_value = int(selected_food_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid selected food id")

    meal_type = (meal_type or "").strip().lower()
    if meal_type not in MEAL_TYPES:
        raise HTTPException(status_code=400, detail="Invalid meal type")

    typed_food = (food_text or "").strip()
    if not typed_food:
        raise HTTPException(status_code=400, detail="Food is required")

    normalized_unit = (unit or "g").strip().lower()
    if normalized_unit not in {"g", "ml"}:
        raise HTTPException(status_code=400, detail="Invalid unit")
    is_manual_override = str(manual_override or "0") in {"1", "true", "on", "yes"}

    conn = get_db_connection()
    daily_meal = get_or_create_daily_meal(conn, user_name, entry_date)

    calories = None
    protein = None
    carbs = None
    fat = None
    food_id = 1

    form_data = {
        "meal_type": meal_type,
        "food_text": typed_food,
        "quantity": quantity,
        "unit": unit,
        "manual_calories": manual_calories,
        "selected_food_id": selected_food_id_value or "",
        "manual_override": "1" if is_manual_override else "0",
    }

    if is_manual_override:
        calories = manual_calories
        food_id = 1

    elif selected_food_id_value:
        matched_food = get_food_by_id(conn, selected_food_id_value)
        if not matched_food:
            response = render_diary_page(
                request,
                conn,
                user_name,
                entry_date,
                error="Selected food was not found.",
                success=None,
                form_data=form_data,
                status_code=400,
            )
            conn.close()
            return response

        food_id = matched_food["id"]
        nutrition = calculate_nutrition(matched_food, quantity, unit)

        if nutrition:
            calories = nutrition["calories"]
            protein = nutrition["protein"]
            carbs = nutrition["carbs"]
            fat = nutrition["fat"]

    else:
        candidates = search_food_matches(conn, typed_food)

        if len(candidates) == 1:
            matched_food = candidates[0]
            food_id = matched_food["id"]
            nutrition = calculate_nutrition(matched_food, quantity, unit)

            if nutrition:
                calories = nutrition["calories"]
                protein = nutrition["protein"]
                carbs = nutrition["carbs"]
                fat = nutrition["fat"]

        elif len(candidates) > 1:
            response = render_diary_page(
                request,
                conn,
                user_name,
                entry_date,
                error="Multiple foods matched. Please choose the correct option or keep manual calories.",
                success=None,
                form_data=form_data,
                match_candidates=candidates,
                status_code=400,
            )
            conn.close()
            return response

    if calories is None:
        response = render_diary_page(
            request,
            conn,
            user_name,
            entry_date,
            error="Food not matched automatically. Please choose a match or enter calories manually.",
            success=None,
            form_data=form_data,
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
            normalized_unit,
            calories,
            protein,
            carbs,
            fat,
        ),
    )

    conn.commit()
    recalculate_daily_meal_total(conn, daily_meal["id"])
    conn.close()

    #   Set session variables
    request.session["last_meal_type"] = meal_type
    request.session["diary_success"] = "Entry saved successfully."
    
    return RedirectResponse(url=f"/diary?entry_date={entry_date}", status_code=303)

#
# Route to delete a diary item
#
@router.post("/diary/delete/{detail_id}")
async def delete_diary_item(request: Request, detail_id: int):
    redirect = login_redirect(request)
    if redirect:
        return redirect    

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

    #   Set session variables
    request.session["diary_success"] = "Entry deleted successfully."

    return RedirectResponse(url=f"/diary?entry_date={entry_date}", status_code=303)

#
# Route to update a diary item
#
@router.post("/diary/update/{detail_id}")
async def update_diary_item(
    request: Request,
    detail_id: int,
    meal_type: str = Form(...),
    food_text: str = Form(...),
    quantity: Optional[float] = Form(None),
    unit: Optional[str] = Form(None),
    manual_calories: Optional[float] = Form(None),
    selected_food_id: Optional[str] = Form(None),
    manual_override: Optional[str] = Form(None),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)

    #   Normalize selected_food_id
    selected_food_id_value = None
    if selected_food_id is not None and str(selected_food_id).strip() != "":
        try:
            selected_food_id_value = int(selected_food_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid selected food id")

    meal_type = (meal_type or "").strip().lower()
    if meal_type not in MEAL_TYPES:
        raise HTTPException(status_code=400, detail="Invalid meal type")

    typed_food = (food_text or "").strip()
    if not typed_food:
        raise HTTPException(status_code=400, detail="Food is required")

    normalized_unit = (unit or "g").strip().lower()
    if normalized_unit not in {"g", "ml"}:
        raise HTTPException(status_code=400, detail="Invalid unit")
    
    is_manual_override = str(manual_override or "0") in {"1", "true", "on", "yes"}

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

    calories = None
    protein = None
    carbs = None
    fat = None
    food_id = 1

    entry_date = existing["entry_date"]

    form_data = {
        "meal_type": meal_type,
        "food_text": typed_food,
        "quantity": quantity,
        "unit": unit,
        "manual_calories": manual_calories,
        "selected_food_id": selected_food_id_value or "",
        "manual_override": "1" if is_manual_override else "0",
    }

    if is_manual_override:
        calories = manual_calories
        food_id = 1

    elif selected_food_id_value:
        matched_food = get_food_by_id(conn, selected_food_id_value)
        if not matched_food:
            response = render_diary_page(
                request,
                conn,
                user_name,
                entry_date,
                error="Selected food was not found.",
                success=None,
                form_data=form_data,
                status_code=400,
            )
            conn.close()
            return response

        food_id = matched_food["id"]
        nutrition = calculate_nutrition(matched_food, quantity, unit)

        if nutrition:
            calories = nutrition["calories"]
            protein = nutrition["protein"]
            carbs = nutrition["carbs"]
            fat = nutrition["fat"]

    else:
        candidates = search_food_matches(conn, typed_food)

        if len(candidates) == 1:
            matched_food = candidates[0]
            food_id = matched_food["id"]
            nutrition = calculate_nutrition(matched_food, quantity, unit)

            if nutrition:
                calories = nutrition["calories"]
                protein = nutrition["protein"]
                carbs = nutrition["carbs"]
                fat = nutrition["fat"]

        elif len(candidates) > 1:
            response = render_diary_page(
                request,
                conn,
                user_name,
                entry_date,
                error="Multiple foods matched. Please choose the correct option or keep manual calories.",
                success=None,
                form_data=form_data,
                match_candidates=candidates,
                status_code=400,
            )
            conn.close()
            return response

    if calories is None:
        response = render_diary_page(
            request,
            conn,
            user_name,
            entry_date,
            error="Food not matched automatically. Please choose a match or enter calories manually.",
            success=None,
            form_data=form_data,
            status_code=400,
        )
        conn.close()
        return response

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
            normalized_unit,
            calories,
            protein,
            carbs,
            fat,
            detail_id,
        ),
    )

    conn.commit()
    recalculate_daily_meal_total(conn, existing["daily_meal_id"])
    conn.close()

    #   Set session variables
    request.session["diary_success"] = "Entry updated successfully."

    return RedirectResponse(url=f"/diary?entry_date={entry_date}", status_code=303)
