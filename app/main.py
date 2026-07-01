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
from app.core.auth import get_current_user_name, login_redirect
from app.routers import admin_alias, auth, dashboard, bodymetrics, food_diary, trends, water
from app.db.database import get_db_connection

#   Constants
ACTIVITY_TYPES = {"cardio", "strength", "walking", "sports", "mobility", "other"}
INTENSITY_LEVELS = {"low", "moderate", "high"}

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

#   Include routing paths from other files
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(bodymetrics.router)
app.include_router(food_diary.router)
app.include_router(trends.router)
app.include_router(admin_alias.router)
app.include_router(water.router)

####################################################################################################
#
#                                  Helper Functions Section
#
####################################################################################################

def get_or_create_daily_expenditure(conn, user_name: str, entry_date: str):
    row = conn.execute(
        """
        SELECT id, entry_date, user_name, status, bmr_kcal, activity_kcal, tdee_kcal, net_balance_kcal, notes
        FROM daily_expenditure
        WHERE entry_date = ? AND user_name = ?
        """,
        (entry_date, user_name),
    ).fetchone()

    if row:
        return row

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO daily_expenditure (
            entry_date, user_name, status, bmr_kcal, activity_kcal, tdee_kcal, net_balance_kcal, notes
        )
        VALUES (?, ?, 'partial', 0, 0, 0, 0, NULL)
        """,
        (entry_date, user_name),
    )
    conn.commit()

    return conn.execute(
        """
        SELECT id, entry_date, user_name, status, bmr_kcal, activity_kcal, tdee_kcal, net_balance_kcal, notes
        FROM daily_expenditure
        WHERE id = ?
        """,
        (cur.lastrowid,),
    ).fetchone()


def recalculate_daily_activity_total(conn, expenditure_id: int):
    total = conn.execute(
        """
        SELECT COALESCE(SUM(calories_burned), 0)
        FROM log_activities
        WHERE expenditure_id = ?
        """,
        (expenditure_id,),
    ).fetchone()[0]

    bmr = conn.execute(
        """
        SELECT COALESCE(bmr_kcal, 0)
        FROM daily_expenditure
        WHERE id = ?
        """,
        (expenditure_id,),
    ).fetchone()[0]

    activity_kcal = int(total or 0)
    tdee_kcal = int((bmr or 0) + activity_kcal)

    conn.execute(
        """
        UPDATE daily_expenditure
        SET activity_kcal = ?, tdee_kcal = ?
        WHERE id = ?
        """,
        (activity_kcal, tdee_kcal, expenditure_id),
    )
    conn.commit()

####################################################################################################
#
#                                  Endpoints/Routing Section
#
####################################################################################################

#
#   Activity Route
#
@app.get("/activity", response_class=HTMLResponse)
async def activity_diary(request: Request, entry_date: str = None):
    redirect = login_redirect(request)
    if redirect:
        return redirect    

    user_name = get_current_user_name(request)
    entry_date = entry_date or date.today().isoformat()

    conn = get_db_connection()
    daily_expenditure = get_or_create_daily_expenditure(conn, user_name, entry_date)

    rows = conn.execute(
        """
        SELECT
            id,
            activity_type,
            duration_minutes,
            activity_value,
            activity_label,
            intensity,
            calories_burned,
            notes
        FROM log_activities
        WHERE expenditure_id = ?
        ORDER BY id ASC
        """,
        (daily_expenditure["id"],),
    ).fetchall()

    items = [dict(row) for row in rows]
    conn.close()

    return templates.TemplateResponse(
        request,
        "activity.html",
        {
            "user": request.session.get("user"),
            "entry_date": entry_date,
            "daily_expenditure": dict(daily_expenditure),
            "items": items,
            "last_activity_type": request.session.get("last_activity_type", "walking"),
        },
    )

#
#   Add Activity Route
#
@app.post("/activity/add")
async def add_activity_item(
    request: Request,
    entry_date: str = Form(...),
    activity_type: str = Form(...),
    activity_label: Optional[str] = Form(None),
    duration_minutes: Optional[int] = Form(None),
    activity_value: Optional[str] = Form(None),
    intensity: Optional[str] = Form(None),
    calories_burned: Optional[int] = Form(0),
    notes: Optional[str] = Form(None),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect    

    user_name = get_current_user_name(request)

    activity_type = (activity_type or "").strip().lower()
    intensity = (intensity or "").strip().lower() if intensity else None
    activity_label = (activity_label or "").strip()
    activity_value = (activity_value or "").strip() or None
    notes = (notes or "").strip() or None

    if activity_type not in ACTIVITY_TYPES:
        raise HTTPException(status_code=400, detail="Invalid activity type")

    if intensity and intensity not in INTENSITY_LEVELS:
        raise HTTPException(status_code=400, detail="Invalid intensity")

    if not activity_label:
        raise HTTPException(status_code=400, detail="Activity label is required")

    conn = get_db_connection()
    daily_expenditure = get_or_create_daily_expenditure(conn, user_name, entry_date)

    conn.execute(
        """
        INSERT INTO log_activities (
            expenditure_id,
            activity_type,
            duration_minutes,
            activity_value,
            activity_label,
            intensity,
            calories_burned,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            daily_expenditure["id"],
            activity_type,
            duration_minutes,
            activity_value,
            activity_label,
            intensity,
            calories_burned or 0,
            notes,
        ),
    )

    conn.commit()
    recalculate_daily_activity_total(conn, daily_expenditure["id"])
    conn.close()

    request.session["last_activity_type"] = activity_type
    return RedirectResponse(url=f"/activity?entry_date={entry_date}", status_code=303)

#
#   Update Activity Route
#
@app.post("/activity/update/{detail_id}")
async def update_activity_item(
    request: Request,
    detail_id: int,
    activity_type: str = Form(...),
    activity_label: Optional[str] = Form(None),
    duration_minutes: Optional[int] = Form(None),
    activity_value: Optional[str] = Form(None),
    intensity: Optional[str] = Form(None),
    calories_burned: Optional[int] = Form(0),
    notes: Optional[str] = Form(None),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect    

    user_name = get_current_user_name(request)

    activity_type = (activity_type or "").strip().lower()
    intensity = (intensity or "").strip().lower() if intensity else None
    activity_label = (activity_label or "").strip()
    activity_value = (activity_value or "").strip() or None
    notes = (notes or "").strip() or None

    if activity_type not in ACTIVITY_TYPES:
        raise HTTPException(status_code=400, detail="Invalid activity type")

    if intensity and intensity not in INTENSITY_LEVELS:
        raise HTTPException(status_code=400, detail="Invalid intensity")

    if not activity_label:
        raise HTTPException(status_code=400, detail="Activity label is required")

    conn = get_db_connection()

    existing = conn.execute(
        """
        SELECT la.id, la.expenditure_id, de.entry_date, de.user_name
        FROM log_activities la
        JOIN daily_expenditure de ON de.id = la.expenditure_id
        WHERE la.id = ?
        """,
        (detail_id,),
    ).fetchone()

    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Activity item not found")

    if existing["user_name"] != user_name:
        conn.close()
        raise HTTPException(status_code=403, detail="Forbidden")

    conn.execute(
        """
        UPDATE log_activities
        SET
            activity_type = ?,
            duration_minutes = ?,
            activity_value = ?,
            activity_label = ?,
            intensity = ?,
            calories_burned = ?,
            notes = ?
        WHERE id = ?
        """,
        (
            activity_type,
            duration_minutes,
            activity_value,
            activity_label,
            intensity,
            calories_burned or 0,
            notes,
            detail_id,
        ),
    )

    conn.commit()
    recalculate_daily_activity_total(conn, existing["expenditure_id"])
    conn.close()

    request.session["last_activity_type"] = activity_type
    return RedirectResponse(url=f"/activity?entry_date={existing['entry_date']}", status_code=303)

#
#   Delete Activity Route
#
@app.post("/activity/delete/{detail_id}")
async def delete_activity_item(request: Request, detail_id: int):
    redirect = login_redirect(request)
    if redirect:
        return redirect    

    user_name = get_current_user_name(request)
    conn = get_db_connection()

    row = conn.execute(
        """
        SELECT la.id, la.expenditure_id, de.entry_date, de.user_name
        FROM log_activities la
        JOIN daily_expenditure de ON de.id = la.expenditure_id
        WHERE la.id = ?
        """,
        (detail_id,),
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Activity item not found")

    if row["user_name"] != user_name:
        conn.close()
        raise HTTPException(status_code=403, detail="Forbidden")

    conn.execute("DELETE FROM log_activities WHERE id = ?", (detail_id,))
    conn.commit()
    recalculate_daily_activity_total(conn, row["expenditure_id"])
    entry_date = row["entry_date"]
    conn.close()

    return RedirectResponse(url=f"/activity?entry_date={entry_date}", status_code=303)

