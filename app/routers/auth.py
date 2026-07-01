from fastapi import APIRouter, Form, Request
from starlette.responses import RedirectResponse, Response

from app.core.security import verify_password, hash_password
from app.core.templates import templates
from app.core.auth import get_current_user_name, login_redirect, load_profile
from app.db.database import get_db_connection

router = APIRouter()

#   Constants
ACTIVITY_LEVELS = {
    "sedentary": "Sedentary",
    "light": "Light",
    "moderate": "Moderate",
    "very_active": "Very active",
    "extra_active": "Extra active",
}

SEX_OPTIONS = {"male", "female"}

#
#   Endpoint for the inicial landing
#
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
    user_name = user_name.strip()
    
    conn = get_db_connection()
    user = conn.execute("""
        SELECT id, user_name, email, password_hash, display_name, is_active, must_change_password
        FROM users
        WHERE user_name = ?
    """, (user_name,)).fetchone()
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
        "is_admin": user["user_name"] == "admin",
    }

    request.session["remember_me"] = bool(remember_me)

    if user["must_change_password"]:
        return RedirectResponse(url="/force-password-reset", status_code=303)

    return RedirectResponse(url="/dashboard", status_code=303)

#
#   Logout Endpoint
#
@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)

#
#   Register Endpoint - GET
#
@router.get("/register")
async def register_page(request: Request):
    user = request.session.get("user")
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request,
        "register.html",
        {
            "request": request,
            "user": None,
            "error": None,
            "values": {},
            "activity_levels": ACTIVITY_LEVELS,
        },
    )

#
#   Register Endpoint - POST
#
@router.post("/register")
async def register(
    request: Request,
    user_name: str = Form(...),
    email: str | None = Form(default=None),
    password: str = Form(...),
    confirm_password: str = Form(...),
    display_name: str | None = Form(default=None),
    sex: str = Form(...),
    date_of_birth: str = Form(...),
    height_cm: float = Form(...),
    start_weight_kg: float = Form(...),
    activity_level: str = Form(...),
):
    user_name = user_name.strip()
    email = (email or "").strip() or None
    display_name = (display_name or "").strip() or None
    sex = sex.strip().lower()
    date_of_birth = date_of_birth.strip()
    activity_level = activity_level.strip()

    values = {
        "user_name": user_name,
        "email": email or "",
        "display_name": display_name or "",
        "sex": sex,
        "date_of_birth": date_of_birth,
        "height_cm": height_cm,
        "start_weight_kg": start_weight_kg,
        "activity_level": activity_level,
    }

    if not user_name:
        error = "Username is required."
    elif len(password) < 8:
        error = "Password must have at least 8 characters."
    elif password != confirm_password:
        error = "Passwords do not match."
    elif sex not in SEX_OPTIONS:
        error = "Invalid sex selected."
    elif activity_level not in ACTIVITY_LEVELS:
        error = "Invalid activity level selected."
    else:
        error = None

    if error:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "request": request,
                "user": None,
                "error": error,
                "values": values,
                "activity_levels": ACTIVITY_LEVELS,
            },
            status_code=400,
        )

    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "request": request,
                "user": None,
                "error": str(exc),
                "values": values,
                "activity_levels": ACTIVITY_LEVELS,
            },
            status_code=400,
        )

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (
                user_name,
                email,
                password_hash,
                display_name,
                is_active,
                sex,
                date_of_birth,
                height_cm,
                start_weight_kg,
                activity_level
            )
            VALUES (?, ?, ?, ?, TRUE, ?, ?, ?, ?, ?)
            """,
            (
                user_name,
                email,
                password_hash,
                display_name,
                sex,
                date_of_birth,
                height_cm,
                start_weight_kg,
                activity_level,
            ),
        )
        conn.commit()

        user_id = cursor.lastrowid
    except Exception:
        conn.close()
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "request": request,
                "user": None,
                "error": "Username or email already exists.",
                "values": values,
                "activity_levels": ACTIVITY_LEVELS,
            },
            status_code=400,
        )

    conn.close()

    request.session["user"] = {
        "id": user_id,
        "user_name": user_name,
        "email": email,
        "name": display_name or user_name,
    }

    return RedirectResponse(url="/dashboard", status_code=303)

#
#   Settings Router - GET
#
@router.get("/settings")
async def settings_page(request: Request):
    redirect = login_redirect(request)
    if redirect:
        return redirect    

    user_name = get_current_user_name(request)

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "request": request,
            "user": request.session.get("user"),
            "profile": load_profile(user_name),
            "error": None,
            "success": None,
            "activity_levels": {
                "sedentary": "Sedentary",
                "light": "Light",
                "moderate": "Moderate",
                "very_active": "Very active",
                "extra_active": "Extra active",
            },
        },
    )

#
#   Settings Router - POST
#
@router.post("/settings")
async def update_settings(
    request: Request,
    email: str | None = Form(default=None),
    display_name: str | None = Form(default=None),
    sex: str = Form(...),
    date_of_birth: str = Form(...),
    height_cm: float = Form(...),
    start_weight_kg: float = Form(...),
    activity_level: str = Form(...),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect    

    user_name = get_current_user_name(request)

    email = (email or "").strip() or None
    display_name = (display_name or "").strip() or None
    sex = sex.strip().lower()
    date_of_birth = date_of_birth.strip()
    activity_level = activity_level.strip()

    activity_levels = {
        "sedentary": "Sedentary",
        "light": "Light",
        "moderate": "Moderate",
        "very_active": "Very active",
        "extra_active": "Extra active",
    }

    profile = {
        "user_name": user_name,
        "email": email or "",
        "display_name": display_name or "",
        "sex": sex,
        "date_of_birth": date_of_birth,
        "height_cm": height_cm,
        "start_weight_kg": start_weight_kg,
        "activity_level": activity_level,
    }

    if sex not in {"male", "female"}:
        error = "Invalid sex selected."
    elif activity_level not in activity_levels:
        error = "Invalid activity level selected."
    else:
        error = None

    if error:
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "request": request,
                "user": request.session.get("user"),
                "profile": profile,
                "error": error,
                "success": None,
                "activity_levels": activity_levels,
            },
            status_code=400,
        )

    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE users
            SET email = ?,
                display_name = ?,
                sex = ?,
                date_of_birth = ?,
                height_cm = ?,
                start_weight_kg = ?,
                activity_level = ?
            WHERE user_name = ?
            """,
            (
                email,
                display_name,
                sex,
                date_of_birth,
                height_cm,
                start_weight_kg,
                activity_level,
                user_name,
            ),
        )
        conn.commit()
    except Exception:
        conn.close()
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "request": request,
                "user": request.session.get("user"),
                "profile": profile,
                "error": "Could not update profile.",
                "success": None,
                "activity_levels": activity_levels,
            },
            status_code=400,
        )

    conn.close()

    #   Update current session information
    session_user = request.session.get("user")
    if session_user:
        session_user["email"] = email
        session_user["name"] = display_name or user_name
        request.session["user"] = session_user

    profile["display_name"] = display_name or ""
    profile["email"] = email or ""

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "request": request,
            "user": request.session.get("user"),
            "profile": profile,
            "error": None,
            "success": "Profile updated successfully.",
            "activity_levels": activity_levels,
        },
    )

#
#   Force Password Reset Endpoint - GET
#
@router.get("/force-password-reset")
async def force_password_reset_page(request: Request):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user = request.session.get("user")
    return templates.TemplateResponse(
        request,
        "force_password_reset.html",
        {
            "request": request,
            "user": user,
            "error": None,
            "success": None,
        },
    )

#
#   Force Password Reset Endpoint - POST
#
@router.post("/force-password-reset")
async def force_password_reset(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)

    if len(new_password) < 8:
        error = "Password must have at least 8 characters."
    elif new_password != confirm_password:
        error = "Passwords do not match."
    else:
        error = None

    if error:
        return templates.TemplateResponse(
            request,
            "force_password_reset.html",
            {
                "request": request,
                "user": request.session.get("user"),
                "error": error,
                "success": None,
            },
            status_code=400,
        )

    conn = get_db_connection()
    user = conn.execute(
        """
        SELECT password_hash
        FROM users
        WHERE user_name = ?
        """,
        (user_name,),
    ).fetchone()

    if not user or not verify_password(current_password, user["password_hash"]):
        conn.close()
        return templates.TemplateResponse(
            request,
            "force_password_reset.html",
            {
                "request": request,
                "user": request.session.get("user"),
                "error": "Current password is incorrect.",
                "success": None,
            },
            status_code=400,
        )

    new_hash = hash_password(new_password)

    conn.execute(
        """
        UPDATE users
        SET password_hash = ?, must_change_password = FALSE
        WHERE user_name = ?
        """,
        (new_hash, user_name),
    )
    conn.commit()
    conn.close()

    return RedirectResponse(url="/dashboard", status_code=303)

#
#   Chaange Password Endpoint - POST
#
@router.post("/settings/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user_name = get_current_user_name(request)

    if len(new_password) < 8:
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "request": request,
                "user": request.session.get("user"),
                "profile": load_profile(user_name),
                "password_error": "Password must have at least 8 characters.",
                "success": None,
                "activity_levels": ACTIVITY_LEVELS,
                "password_modal_open": True,
            },
            status_code=400,
        )

    if new_password != confirm_password:
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "request": request,
                "user": request.session.get("user"),
                "profile": load_profile(user_name),
                "password_error": "Passwords do not match.",
                "success": None,
                "activity_levels": ACTIVITY_LEVELS,
                "password_modal_open": True,
            },
            status_code=400,
        )

    conn = get_db_connection()
    user = conn.execute(
        "SELECT password_hash FROM users WHERE user_name = ?",
        (user_name,),
    ).fetchone()

    if not user or not verify_password(current_password, user["password_hash"]):
        conn.close()
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "request": request,
                "user": request.session.get("user"),
                "profile": load_profile(user_name),
                "password_error": "Current password is incorrect.",
                "success": None,
                "activity_levels": ACTIVITY_LEVELS,
                "password_modal_open": True,
            },
            status_code=400,
        )

    conn.execute(
        "UPDATE users SET password_hash = ?, must_change_password = FALSE WHERE user_name = ?",
        (hash_password(new_password), user_name),
    )
    conn.commit()
    conn.close()

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "request": request,
            "user": request.session.get("user"),
            "profile": load_profile(user_name),
            "password_error": None,
            "success": "Password updated successfully.",
            "activity_levels": ACTIVITY_LEVELS,
            "password_modal_open": False,
        },
    )