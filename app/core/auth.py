from fastapi import HTTPException, Request
from starlette.responses import RedirectResponse
from app.db.database import get_db_connection

def get_current_user(request: Request):
    return request.session.get("user")

def get_current_user_name(request: Request) -> str:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user.get("user_name") or user.get("username") or user.get("name")

def login_redirect(request: Request):
    if not get_current_user(request):
        return RedirectResponse(url="/login", status_code=303)
    return None

def load_profile(user_name: str):
    conn = get_db_connection()
    profile = conn.execute(
        """
        SELECT user_name, email, display_name, sex, date_of_birth,
               height_cm, start_weight_kg, activity_level
        FROM users
        WHERE user_name = ?
        """,
        (user_name,),
    ).fetchone()
    conn.close()
    return profile