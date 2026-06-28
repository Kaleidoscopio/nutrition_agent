from fastapi import APIRouter, Request

from app.core.auth import get_current_user_name, login_redirect
from app.core.templates import templates
from app.services.dashboard_service import get_dashboard_stats

router = APIRouter()

#
#   Dashboard Router - GET
#
@router.get("/dashboard")
async def dashboard(request: Request):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)
    stats = get_dashboard_stats(user_name)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "user": request.session.get("user"),
            "stats": stats,
        },
    )