from fastapi import APIRouter, Form, Request
from datetime import date
from app.core.auth import get_current_user_name, login_redirect
from app.core.templates import templates
from app.db.database import get_db_connection
from app.services.body_metrics_service import calculate_bmi
from starlette.responses import RedirectResponse

router = APIRouter()

#
#   Body-Metrics Router - GET
#
@router.get("/body-metrics")
async def body_metrics_page(request: Request, entry_date: str | None = None, saved: int | None = None):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)
    entry_date = entry_date or date.today().isoformat()
    success = "Body metrics saved successfully." if saved == 1 else None

    conn = get_db_connection()
    current = conn.execute(
        """
        SELECT entry_date, weight_kg, body_fat_pct, muscle_mass_pct
        FROM body_metrics
        WHERE user_name = ?
          AND entry_date = ?
        LIMIT 1
        """,
        (user_name, entry_date),
    ).fetchone()
    conn.close()

    profile = {
        "entry_date": entry_date,
        "weight_kg": current["weight_kg"] if current else "",
        "body_fat_pct": current["body_fat_pct"] if current else "",
        "muscle_mass_pct": current["muscle_mass_pct"] if current else "",
    }

    return templates.TemplateResponse(
        request,
        "body_metrics.html",
        {
            "request": request,
            "user": request.session.get("user"),
            "profile": profile,
            "error": None,
            "success": success,
        },
    )

#
#   Body-Metrics Router - POST
#
@router.post("/body-metrics")
async def add_body_metrics(
    request: Request,
    entry_date: str = Form(...),
    weight_kg: float = Form(...),
    body_fat_pct: float | None = Form(default=None),
    muscle_mass_pct: float | None = Form(default=None),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)

    conn = get_db_connection()
    user_profile = conn.execute(
        """
        SELECT height_cm
        FROM users
        WHERE user_name = ?
        LIMIT 1
        """,
        (user_name,),
    ).fetchone()

    height_cm = user_profile["height_cm"] if user_profile else None
    bmi = calculate_bmi(weight_kg, height_cm)

    #   Store current info
    profile = {
        "entry_date": entry_date,
        "weight_kg": weight_kg,
        "body_fat_pct": body_fat_pct or "",
        "muscle_mass_pct": muscle_mass_pct or "",
    }

    try:
        conn.execute(
            """
            INSERT INTO body_metrics (
                user_name,
                entry_date,
                weight_kg,
                body_fat_pct,
                muscle_mass_pct,
                bmi
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_name, entry_date)
            DO UPDATE SET
                weight_kg = excluded.weight_kg,
                body_fat_pct = COALESCE(excluded.body_fat_pct, body_metrics.body_fat_pct),
                muscle_mass_pct = COALESCE(excluded.muscle_mass_pct, body_metrics.muscle_mass_pct),
                bmi = excluded.bmi
            """,
            (
                user_name,
                entry_date,
                weight_kg,
                body_fat_pct,
                muscle_mass_pct,
                bmi,
            ),
        )
        conn.commit()
    except Exception:
        conn.close()
        return templates.TemplateResponse(
            request,
            "body_metrics.html",
            {
                "request": request,
                "user": request.session.get("user"),
                "error": "Could not save body metrics.",
                "success": None,
                "profile": profile,
            },
            status_code=400,
        )

    conn.close()
    return RedirectResponse(
        url=f"/body-metrics?entry_date={entry_date}&saved=1",
        status_code=303,
    )