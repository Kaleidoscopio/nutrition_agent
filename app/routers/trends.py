from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.auth import get_current_user_name, login_redirect
from app.core.templates import templates
from app.db.database import get_db_connection
from app.services.trends_service import build_trends_payload, parse_period

router = APIRouter()

#
#   Trends Routing
#
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

#
#   Trends API?
#
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