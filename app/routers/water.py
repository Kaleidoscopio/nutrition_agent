from datetime import date
from fastapi import APIRouter, Form, Request
from starlette.responses import RedirectResponse
from app.core.auth import get_current_user_name, login_redirect
from app.core.templates import templates
from app.db.database import get_db_connection

router = APIRouter()


@router.get("/water")
async def water_page(
    request: Request,
    entry_date: str | None = None,
    saved: int | None = None,
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)
    entry_date = entry_date or date.today().isoformat()

    conn = get_db_connection()
    current = conn.execute(
        """
        SELECT entry_date, target_ml, consumed_ml, notes
        FROM daily_water
        WHERE user_name = ?
          AND entry_date = ?
        LIMIT 1
        """,
        (user_name, entry_date),
    ).fetchone()
    conn.close()

    profile = {
        "entry_date": entry_date,
        "target_ml": current["target_ml"] if current else 2000,
        "consumed_ml": current["consumed_ml"] if current else 0,
        "notes": current["notes"] if current else "",
    }

    success = "Water intake updated." if saved == 1 else None

    return templates.TemplateResponse(
        request,
        "water.html",
        {
            "request": request,
            "user": request.session.get("user"),
            "profile": profile,
            "error": None,
            "success": success,
        },
    )


@router.post("/water/add")
async def add_water(
    request: Request,
    entry_date: str = Form(...),
    amount_ml: int = Form(...),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)
    amount_ml = max(0, amount_ml)

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO daily_water (entry_date, user_name, target_ml, consumed_ml, notes)
        VALUES (?, ?, 2000, ?, NULL)
        ON CONFLICT(entry_date, user_name)
        DO UPDATE SET consumed_ml = daily_water.consumed_ml + excluded.consumed_ml
        """,
        (entry_date, user_name, amount_ml),
    )
    conn.commit()
    conn.close()

    return RedirectResponse(
        url=f"/water?entry_date={entry_date}&saved=1",
        status_code=303,
    )


@router.post("/water/update")
async def update_water(
    request: Request,
    entry_date: str = Form(...),
    target_ml: int = Form(...),
    consumed_ml: int = Form(...),
    notes: str | None = Form(default=None),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)
    target_ml = max(0, target_ml)
    consumed_ml = max(0, consumed_ml)
    notes = (notes or "").strip() or None

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO daily_water (entry_date, user_name, target_ml, consumed_ml, notes)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(entry_date, user_name)
        DO UPDATE SET
            target_ml = excluded.target_ml,
            consumed_ml = excluded.consumed_ml,
            notes = excluded.notes
        """,
        (entry_date, user_name, target_ml, consumed_ml, notes),
    )
    conn.commit()
    conn.close()

    return RedirectResponse(
        url=f"/water?entry_date={entry_date}&saved=1",
        status_code=303,
    )