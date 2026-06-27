from fastapi import APIRouter, Form, Request
from starlette.responses import RedirectResponse, Response

from app.core.security import verify_password
from app.core.templates import templates
from app.db.database import get_db_connection

router = APIRouter()


@router.get("/")
async def home(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse(
        request,
        "home.html",
        {"request": request, "user": user},
    )


@router.get("/login")
async def login_page(request: Request):
    user = request.session.get("user")
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "user": None, "error": None},
    )


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    user_name: str = Form(...),
    password: str = Form(...),
    remember_me: str | None = Form(default=None),
):
    conn = get_db_connection()
    user = conn.execute("""
        SELECT id, user_name, email, password_hash, display_name, is_active
        FROM users
        WHERE user_name = ?
    """, (user_name.strip(),)).fetchone()
    conn.close()

    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "user": None,
                "error": "Invalid username or password."
            },
            status_code=400,
        )

    if not user["is_active"]:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "user": None,
                "error": "This account is disabled."
            },
            status_code=403,
        )

    request.session["user"] = {
        "id": user["id"],
        "user_name": user["user_name"],
        "email": user["email"],
        "name": user["display_name"] or user["user_name"],
    }

    redirect = RedirectResponse(url="/dashboard", status_code=303)

    if remember_me:
        request.session["remember_me"] = True
    else:
        request.session["remember_me"] = False

    return redirect


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)