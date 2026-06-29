from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.core.auth import login_redirect
from app.core.templates import templates
from app.db.database import get_db_connection

router = APIRouter()

def require_admin(request: Request):
    user = request.session.get("user")
    if not user or user.get("user_name") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user

def load_food_options(conn, search: str | None = None):
    query = """
        SELECT id, food_name, food_category
        FROM food_master
        WHERE 1 = 1
    """
    params = []

    if search:
        query += " AND (food_name LIKE ? OR search_text LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY food_name ASC LIMIT 100"
    return conn.execute(query, params).fetchall()

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, q: str | None = None):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user = require_admin(request)

    conn = get_db_connection()

    alias_query = """
        SELECT
            fa.id,
            fa.alias,
            fa.food_id,
            fm.food_name,
            fm.food_category
        FROM food_alias fa
        JOIN food_master fm ON fm.id = fa.food_id
        WHERE 1 = 1
    """
    params = []

    if q:
        alias_query += " AND (fa.alias LIKE ? OR fm.food_name LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])

    alias_query += " ORDER BY fa.alias ASC"

    aliases = conn.execute(alias_query, params).fetchall()
    foods = load_food_options(conn)
    conn.close()

    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "request": request,
            "user": user,
            "aliases": aliases,
            "foods": foods,
            "query": q or "",
            "error": None,
            "success": None,
        },
    )

@router.post("/admin/food-alias/add")
async def add_food_alias(
    request: Request,
    food_id: int = Form(...),
    alias: str = Form(...),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user = require_admin(request)
    alias = alias.strip()

    conn = get_db_connection()

    if not alias:
        aliases = conn.execute("""
            SELECT fa.id, fa.alias, fa.food_id, fm.food_name, fm.food_category
            FROM food_alias fa
            JOIN food_master fm ON fm.id = fa.food_id
            ORDER BY fa.alias ASC
        """).fetchall()
        foods = load_food_options(conn)
        conn.close()
        return templates.TemplateResponse(
            request,
            "admin.html",
            {
                "request": request,
                "user": user,
                "aliases": aliases,
                "foods": foods,
                "query": "",
                "error": "Alias is required.",
                "success": None,
            },
            status_code=400,
        )

    duplicate = conn.execute(
        "SELECT id FROM food_alias WHERE lower(alias) = lower(?)",
        (alias,),
    ).fetchone()

    if duplicate:
        aliases = conn.execute("""
            SELECT fa.id, fa.alias, fa.food_id, fm.food_name, fm.food_category
            FROM food_alias fa
            JOIN food_master fm ON fm.id = fa.food_id
            ORDER BY fa.alias ASC
        """).fetchall()
        foods = load_food_options(conn)
        conn.close()
        return templates.TemplateResponse(
            request,
            "admin.html",
            {
                "request": request,
                "user": user,
                "aliases": aliases,
                "foods": foods,
                "query": "",
                "error": "Alias already exists.",
                "success": None,
            },
            status_code=400,
        )

    conn.execute(
        "INSERT INTO food_alias (food_id, alias) VALUES (?, ?)",
        (food_id, alias),
    )
    conn.commit()
    conn.close()

    return RedirectResponse(url="/admin", status_code=303)

@router.post("/admin/food-alias/update/{alias_id}")
async def update_food_alias(
    request: Request,
    alias_id: int,
    food_id: int = Form(...),
    alias: str = Form(...),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    require_admin(request)
    alias = alias.strip()

    conn = get_db_connection()

    duplicate = conn.execute(
        "SELECT id FROM food_alias WHERE lower(alias) = lower(?) AND id <> ?",
        (alias, alias_id),
    ).fetchone()

    if duplicate:
        conn.close()
        return RedirectResponse(url="/admin?error=duplicate", status_code=303)

    conn.execute(
        "UPDATE food_alias SET food_id = ?, alias = ? WHERE id = ?",
        (food_id, alias, alias_id),
    )
    conn.commit()
    conn.close()

    return RedirectResponse(url="/admin", status_code=303)

@router.post("/admin/food-alias/delete/{alias_id}")
async def delete_food_alias(request: Request, alias_id: int):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    require_admin(request)

    conn = get_db_connection()
    conn.execute("DELETE FROM food_alias WHERE id = ?", (alias_id,))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/admin", status_code=303)