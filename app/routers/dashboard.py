from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

from app.core.templates import templates
from app.services.dashboard_service import get_dashboard_stats

router = APIRouter()


@router.get("/dashboard")
async def dashboard(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    stats = get_dashboard_stats(user["user_name"])

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
        },
    )