import csv
import io
import zipfile

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.auth import get_current_user_name, login_redirect
from app.core.templates import templates
from app.db.database import get_db_connection
from app.services.trends_service import (
    build_trends_payload,
    get_period_bounds,
    load_trends_history,
    parse_period,
)

router = APIRouter()


@router.get("/trends")
async def trends_page(request: Request, period: str = "30d"):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)
    period = parse_period(period)

    conn = get_db_connection()
    payload = build_trends_payload(conn, user_name, period)
    conn.close()

    return templates.TemplateResponse(
        request,
        "trends.html",
        {
            "request": request,
            "user": request.session.get("user"),
            "error": None,
            "success": None,
            **payload,
        },
    )


@router.get("/api/trends")
async def trends_api(request: Request, period: str = "30d"):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)
    period = parse_period(period)

    conn = get_db_connection()
    payload = build_trends_payload(conn, user_name, period)
    conn.close()

    return JSONResponse(payload["chart_data"])


@router.get("/trends/export")
async def export_trends(request: Request, period: str = "30d"):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)
    period = parse_period(period)
    start_date, end_date = get_period_bounds(period)

    conn = get_db_connection()
    trends_rows = load_trends_history(conn, user_name, start_date, end_date)
    meal_rows = export_meal_rows(conn, user_name, start_date, end_date)
    conn.close()

    trends_buffer = io.StringIO()
    trends_writer = csv.DictWriter(
        trends_buffer,
        fieldnames=[
            "day",
            "calories_in",
            "calories_out",
            "bmr_kcal",
            "activity_kcal",
            "tdee_kcal",
            "net_balance_kcal",
            "water_consumed_ml",
            "water_target_ml",
            "weight_kg",
            "body_fat_pct",
            "muscle_mass_pct",
            "bmi",
        ],
    )
    trends_writer.writeheader()
    for row in trends_rows:
        trends_writer.writerow(row)

    meals_buffer = io.StringIO()
    meals_writer = csv.DictWriter(
        meals_buffer,
        fieldnames=[
            "entry_date",
            "daily_meal_id",
            "meal_status",
            "daily_kcal",
            "daily_meal_notes",
            "detail_id",
            "meal_type",
            "food_id",
            "quantity",
            "unit",
            "calories",
            "protein",
            "carbs",
            "fat",
            "food_label",
            "detail_created_at",
        ],
    )
    meals_writer.writeheader()
    for row in meal_rows:
        meals_writer.writerow(row)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(f"trends_detailed_records_{period}.csv", trends_buffer.getvalue())
        zip_file.writestr(f"daily_meals_with_details_{period}.csv", meals_buffer.getvalue())

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="trends_export_{period}.zip"'
        },
    )