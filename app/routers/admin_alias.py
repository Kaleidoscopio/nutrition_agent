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


def load_categories(conn):
    rows = conn.execute(
        """
        SELECT DISTINCT food_category
        FROM food_master
        WHERE food_category IS NOT NULL
          AND TRIM(food_category) <> ''
        ORDER BY food_category ASC
        """
    ).fetchall()
    return [row["food_category"] for row in rows]


def load_food_search_results(conn, query_filter: str | None = None, category_filter: str | None = None):
    if not query_filter and not category_filter:
        return []

    query = """
        SELECT id, food_name, food_category, calories_100g
        FROM food_master
        WHERE 1 = 1
    """
    params = []

    if query_filter:
        query += " AND (food_name LIKE ? OR search_text LIKE ?)"
        params.extend([f"%{query_filter}%", f"%{query_filter}%"])

    if category_filter:
        query += " AND food_category = ?"
        params.append(category_filter)

    query += " ORDER BY food_name ASC LIMIT 25"
    return conn.execute(query, params).fetchall()


def load_selected_food(conn, selected_food_id: int | None):
    if not selected_food_id:
        return None

    return conn.execute(
        """
        SELECT id, food_name, food_category, calories_100g
        FROM food_master
        WHERE id = ?
        """,
        (selected_food_id,),
    ).fetchone()


def load_aliases_for_food(conn, food_id: int):
    return conn.execute(
        """
        SELECT id, alias
        FROM food_alias
        WHERE food_id = ?
        ORDER BY alias ASC
        """,
        (food_id,),
    ).fetchall()


def load_alias_directory(conn, query_filter: str | None = None, category_filter: str | None = None):
    if not query_filter and not category_filter:
        return []

    query = """
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

    if query_filter:
        query += " AND (fa.alias LIKE ? OR fm.food_name LIKE ?)"
        params.extend([f"%{query_filter}%", f"%{query_filter}%"])

    if category_filter:
        query += " AND fm.food_category = ?"
        params.append(category_filter)

    query += " ORDER BY fa.alias ASC LIMIT 100"
    return conn.execute(query, params).fetchall()


def render_admin_page(
    request: Request,
    user,
    query_filter: str = "",
    category_filter: str = "",
    selected_food_id: int | None = None,
    error: str | None = None,
    success: str | None = None,
    status_code: int = 200,
):
    conn = get_db_connection()
    categories = load_categories(conn)
    food_results = load_food_search_results(conn, query_filter, category_filter or None)
    selected_food = load_selected_food(conn, selected_food_id)
    selected_food_aliases = load_aliases_for_food(conn, selected_food_id) if selected_food else []
    alias_directory = load_alias_directory(conn, query_filter, category_filter or None)
    conn.close()

    return templates.TemplateResponse(
        request,
        "admin_alias.html",
        {
            "request": request,
            "user": user,
            "query_filter": query_filter,
            "category_filter": category_filter,
            "categories": categories,
            "food_results": food_results,
            "selected_food": selected_food,
            "selected_food_aliases": selected_food_aliases,
            "alias_directory": alias_directory,
            "show_alias_directory": bool(query_filter or category_filter or selected_food),
            "error": error,
            "success": success,
        },
        status_code=status_code,
    )


@router.get("/admin-alias", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    query_filter: str | None = None,
    category_filter: str | None = None,
    selected_food_id: int | None = None,
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user = require_admin(request)

    return render_admin_page(
        request=request,
        user=user,
        query_filter=(query_filter or "").strip(),
        category_filter=(category_filter or "").strip(),
        selected_food_id=selected_food_id,
    )


@router.post("/admin-alias/food-alias/add")
async def add_food_alias(
    request: Request,
    selected_food_id: int = Form(...),
    query_filter: str = Form(default=""),
    category_filter: str = Form(default=""),
    alias: str = Form(...),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user = require_admin(request)
    alias = alias.strip()

    if not alias:
        return render_admin_page(
            request=request,
            user=user,
            query_filter=query_filter,
            category_filter=category_filter,
            selected_food_id=selected_food_id,
            error="Alias is required.",
            status_code=400,
        )

    conn = get_db_connection()

    duplicate = conn.execute(
        "SELECT id FROM food_alias WHERE lower(alias) = lower(?)",
        (alias,),
    ).fetchone()

    if duplicate:
        conn.close()
        return render_admin_page(
            request=request,
            user=user,
            query_filter=query_filter,
            category_filter=category_filter,
            selected_food_id=selected_food_id,
            error="Alias already exists.",
            status_code=400,
        )

    conn.execute(
        "INSERT INTO food_alias (food_id, alias) VALUES (?, ?)",
        (selected_food_id, alias),
    )
    conn.commit()
    conn.close()

    return RedirectResponse(
        url=f"/admin-alias?query_filter={query_filter}&category_filter={category_filter}&selected_food_id={selected_food_id}",
        status_code=303,
    )


@router.post("/admin-alias/food-alias/update/{alias_id}")
async def update_food_alias(
    request: Request,
    alias_id: int,
    selected_food_id: int = Form(...),
    query_filter: str = Form(default=""),
    category_filter: str = Form(default=""),
    alias: str = Form(...),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user = require_admin(request)
    alias = alias.strip()

    if not alias:
        return render_admin_page(
            request=request,
            user=user,
            query_filter=query_filter,
            category_filter=category_filter,
            selected_food_id=selected_food_id,
            error="Alias is required.",
            status_code=400,
        )

    conn = get_db_connection()

    duplicate = conn.execute(
        "SELECT id FROM food_alias WHERE lower(alias) = lower(?) AND id <> ?",
        (alias, alias_id),
    ).fetchone()

    if duplicate:
        conn.close()
        return render_admin_page(
            request=request,
            user=user,
            query_filter=query_filter,
            category_filter=category_filter,
            selected_food_id=selected_food_id,
            error="Alias already exists.",
            status_code=400,
        )

    conn.execute(
        "UPDATE food_alias SET alias = ? WHERE id = ? AND food_id = ?",
        (alias, alias_id, selected_food_id),
    )
    conn.commit()
    conn.close()

    return RedirectResponse(
        url=f"/admin-alias?query_filter={query_filter}&category_filter={category_filter}&selected_food_id={selected_food_id}",
        status_code=303,
    )


@router.post("/admin-alias/food-alias/delete/{alias_id}")
async def delete_food_alias(
    request: Request,
    alias_id: int,
    selected_food_id: int = Form(...),
    query_filter: str = Form(default=""),
    category_filter: str = Form(default=""),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    require_admin(request)

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM food_alias WHERE id = ? AND food_id = ?",
        (alias_id, selected_food_id),
    )
    conn.commit()
    conn.close()

    return RedirectResponse(
        url=f"/admin-alias?query_filter={query_filter}&category_filter={category_filter}&selected_food_id={selected_food_id}",
        status_code=303,
    )