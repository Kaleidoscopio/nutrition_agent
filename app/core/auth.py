from fastapi import Request
from starlette.responses import RedirectResponse


def get_current_user(request: Request):
    return request.session.get("user")


def require_user(request: Request):
    user = get_current_user(request)
    if not user:
        return None
    return user


def login_redirect():
    return RedirectResponse(url="/login", status_code=303)