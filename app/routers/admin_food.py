from urllib.parse import urlencode

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.auth import login_redirect
from app.core.templates import templates
from app.db.database import get_db_connection
from app.core.text import normalize_text

router = APIRouter()

FORM_DEFAULTS = {
    "food_name": "",
    "food_category": "",
    "calories_100g": "",
    "protein_100g": "",
    "carbs_100g": "",
    "fat_100g": "",
    "fiber_100g": "",
    "sugar_100g": "",
    "salt_100g": "",
    "source": "",
    "source_food_id": "",
}


def require_admin(request: Request):
    user = request.session.get("user")
    if not user or user.get("user_name") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


def build_admin_url(query_filter: str = "", category_filter: str = "", selected_food_id: int | None = None):
    params = {}
    if query_filter:
        params["query_filter"] = query_filter
    if category_filter:
        params["category_filter"] = category_filter
    if selected_food_id:
        params["selected_food_id"] = selected_food_id
    return "/admin-food" if not params else f"/admin-food?{urlencode(params)}"

def to_float_or_none(value: str, label: str):
    value = (value or "").strip()
    if value == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid number.") from exc


def parse_food_form(
    food_name: str,
    food_category: str,
    calories_100g: str,
    protein_100g: str,
    carbs_100g: str,
    fat_100g: str,
    fiber_100g: str,
    sugar_100g: str,
    salt_100g: str,
    source: str,
    source_food_id: str,
):
    parsed = {
        "food_name": food_name.strip(),
        "food_category": food_category.strip() or None,
        "source": source.strip(),
        "source_food_id": source_food_id.strip(),
        "calories_100g": to_float_or_none(calories_100g, "Calories / 100g"),
        "protein_100g": to_float_or_none(protein_100g, "Protein / 100g"),
        "carbs_100g": to_float_or_none(carbs_100g, "Carbs / 100g"),
        "fat_100g": to_float_or_none(fat_100g, "Fat / 100g"),
        "fiber_100g": to_float_or_none(fiber_100g, "Fiber / 100g"),
        "sugar_100g": to_float_or_none(sugar_100g, "Sugar / 100g"),
        "salt_100g": to_float_or_none(salt_100g, "Salt / 100g"),
    }

    if not parsed["food_name"]:
        raise ValueError("Food name is required.")
    if not parsed["source"]:
        raise ValueError("Source is required.")
    if not parsed["source_food_id"]:
        raise ValueError("Source food id is required.")

    return parsed


def food_form_from_record(record=None, override=None):
    values = dict(FORM_DEFAULTS)
    if record:
        for key in values:
            raw = record[key] if key in record.keys() else None
            values[key] = "" if raw is None else str(raw)
    if override:
        for key, value in override.items():
            if key in values:
                values[key] = "" if value is None else str(value)
    return values


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
    query = """
        SELECT id, food_name, food_category, calories_100g, source, source_food_id
        FROM food_master
        WHERE 1 = 1
    """
    params = []

    if query_filter:
        wildcard_name = f"%{query_filter.strip()}%"
        wildcard_search = f"%{normalize_text(query_filter)}%"
        query += " AND (food_name LIKE ? OR search_text LIKE ? OR source_food_id LIKE ?)"
        params.extend([wildcard_name, wildcard_search, wildcard_name])

    if category_filter:
        query += " AND food_category = ?"
        params.append(category_filter)

    query += " ORDER BY food_name ASC LIMIT 50"
    return conn.execute(query, params).fetchall()


def load_selected_food(conn, selected_food_id: int | None):
    if not selected_food_id:
        return None

    return conn.execute(
        """
        SELECT
            id,
            food_name,
            search_text,
            food_category,
            calories_100g,
            protein_100g,
            carbs_100g,
            fat_100g,
            fiber_100g,
            sugar_100g,
            salt_100g,
            source,
            source_food_id,
            created_at
        FROM food_master
        WHERE id = ?
        """,
        (selected_food_id,),
    ).fetchone()


def ensure_food_master_unique(conn, source: str, source_food_id: str, exclude_id: int | None = None):
    query = "SELECT id FROM food_master WHERE source = ? AND source_food_id = ?"
    params = [source, source_food_id]
    if exclude_id is not None:
        query += " AND id <> ?"
        params.append(exclude_id)

    duplicate = conn.execute(query, params).fetchone()
    if duplicate:
        raise ValueError("A food with the same source and source food id already exists.")


def render_admin_page(
    request: Request,
    user,
    query_filter: str = "",
    category_filter: str = "",
    selected_food_id: int | None = None,
    error: str | None = None,
    success: str | None = None,
    status_code: int = 200,
    form_values: dict | None = None,
):
    conn = get_db_connection()
    categories = load_categories(conn)
    food_results = load_food_search_results(conn, query_filter or None, category_filter or None)
    selected_food = load_selected_food(conn, selected_food_id)
    conn.close()

    effective_form = food_form_from_record(selected_food, form_values)

    return templates.TemplateResponse(
        request,
        "admin_food.html",
        {
            "request": request,
            "user": user,
            "query_filter": query_filter,
            "category_filter": category_filter,
            "categories": categories,
            "food_results": food_results,
            "selected_food": selected_food,
            "food_form": effective_form,
            "error": error,
            "success": success,
        },
        status_code=status_code,
    )


@router.get("/admin-food", response_class=HTMLResponse)
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


@router.post("/admin-food/food-master/create")
async def create_food_master(
    request: Request,
    query_filter: str = Form(default=""),
    category_filter: str = Form(default=""),
    food_name: str = Form(...),
    food_category: str = Form(default=""),
    calories_100g: str = Form(default=""),
    protein_100g: str = Form(default=""),
    carbs_100g: str = Form(default=""),
    fat_100g: str = Form(default=""),
    fiber_100g: str = Form(default=""),
    sugar_100g: str = Form(default=""),
    salt_100g: str = Form(default=""),
    source: str = Form(...),
    source_food_id: str = Form(...),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user = require_admin(request)

    search_text = normalize_text(food_name)

    raw_form = {
        "food_name": food_name,
        "food_category": food_category,
        "calories_100g": calories_100g,
        "protein_100g": protein_100g,
        "carbs_100g": carbs_100g,
        "fat_100g": fat_100g,
        "fiber_100g": fiber_100g,
        "sugar_100g": sugar_100g,
        "salt_100g": salt_100g,
        "source": source,
        "source_food_id": source_food_id,
    }

    try:
        parsed = parse_food_form(**raw_form)
    except ValueError as exc:
        return render_admin_page(
            request=request,
            user=user,
            query_filter=query_filter.strip(),
            category_filter=category_filter.strip(),
            error=str(exc),
            status_code=400,
            form_values=raw_form,
        )

    conn = get_db_connection()
    try:
        ensure_food_master_unique(conn, parsed["source"], parsed["source_food_id"])
        cursor = conn.execute(
            """
            INSERT INTO food_master (
                food_name,
                search_text,
                food_category,
                calories_100g,
                protein_100g,
                carbs_100g,
                fat_100g,
                fiber_100g,
                sugar_100g,
                salt_100g,
                source,
                source_food_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                parsed["food_name"],
                search_text,
                parsed["food_category"],
                parsed["calories_100g"],
                parsed["protein_100g"],
                parsed["carbs_100g"],
                parsed["fat_100g"],
                parsed["fiber_100g"],
                parsed["sugar_100g"],
                parsed["salt_100g"],
                parsed["source"],
                parsed["source_food_id"],
            ),
        )
        conn.commit()
        new_food_id = cursor.lastrowid
    except ValueError as exc:
        conn.close()
        return render_admin_page(
            request=request,
            user=user,
            query_filter=query_filter.strip(),
            category_filter=category_filter.strip(),
            error=str(exc),
            status_code=400,
            form_values=raw_form,
        )
    conn.close()

    return RedirectResponse(
        url=build_admin_url(query_filter.strip(), category_filter.strip(), new_food_id),
        status_code=303,
    )


@router.post("/admin-food/food-master/update/{food_id}")
async def update_food_master(
    request: Request,
    food_id: int,
    query_filter: str = Form(default=""),
    category_filter: str = Form(default=""),
    food_name: str = Form(...),
    food_category: str = Form(default=""),
    calories_100g: str = Form(default=""),
    protein_100g: str = Form(default=""),
    carbs_100g: str = Form(default=""),
    fat_100g: str = Form(default=""),
    fiber_100g: str = Form(default=""),
    sugar_100g: str = Form(default=""),
    salt_100g: str = Form(default=""),
    source: str = Form(...),
    source_food_id: str = Form(...),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user = require_admin(request)

    search_text = normalize_text(food_name)

    raw_form = {
        "food_name": food_name,
        "food_category": food_category,
        "calories_100g": calories_100g,
        "protein_100g": protein_100g,
        "carbs_100g": carbs_100g,
        "fat_100g": fat_100g,
        "fiber_100g": fiber_100g,
        "sugar_100g": sugar_100g,
        "salt_100g": salt_100g,
        "source": source,
        "source_food_id": source_food_id,
    }

    try:
        parsed = parse_food_form(**raw_form)
    except ValueError as exc:
        return render_admin_page(
            request=request,
            user=user,
            query_filter=query_filter.strip(),
            category_filter=category_filter.strip(),
            selected_food_id=food_id,
            error=str(exc),
            status_code=400,
            form_values=raw_form,
        )

    conn = get_db_connection()
    existing = load_selected_food(conn, food_id)
    if not existing:
        conn.close()
        return render_admin_page(
            request=request,
            user=user,
            query_filter=query_filter.strip(),
            category_filter=category_filter.strip(),
            error="Food not found.",
            status_code=404,
            form_values=raw_form,
        )

    try:
        ensure_food_master_unique(conn, parsed["source"], parsed["source_food_id"], exclude_id=food_id)
        conn.execute(
            """
            UPDATE food_master
            SET food_name = ?,
                search_text = ?,
                food_category = ?,
                calories_100g = ?,
                protein_100g = ?,
                carbs_100g = ?,
                fat_100g = ?,
                fiber_100g = ?,
                sugar_100g = ?,
                salt_100g = ?,
                source = ?,
                source_food_id = ?
            WHERE id = ?
            """,
            (
                parsed["food_name"],
                search_text,
                parsed["food_category"],
                parsed["calories_100g"],
                parsed["protein_100g"],
                parsed["carbs_100g"],
                parsed["fat_100g"],
                parsed["fiber_100g"],
                parsed["sugar_100g"],
                parsed["salt_100g"],
                parsed["source"],
                parsed["source_food_id"],
                food_id,
            ),
        )
        conn.commit()
    except ValueError as exc:
        conn.close()
        return render_admin_page(
            request=request,
            user=user,
            query_filter=query_filter.strip(),
            category_filter=category_filter.strip(),
            selected_food_id=food_id,
            error=str(exc),
            status_code=400,
            form_values=raw_form,
        )
    conn.close()

    return RedirectResponse(
        url=build_admin_url(query_filter.strip(), category_filter.strip(), food_id),
        status_code=303,
    )


@router.post("/admin-food/food-master/delete/{food_id}")
async def delete_food_master(
    request: Request,
    food_id: int,
    query_filter: str = Form(default=""),
    category_filter: str = Form(default=""),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user = require_admin(request)
    conn = get_db_connection()
    existing = load_selected_food(conn, food_id)
    if not existing:
        conn.close()
        return render_admin_page(
            request=request,
            user=user,
            query_filter=query_filter.strip(),
            category_filter=category_filter.strip(),
            error="Food not found.",
            status_code=404,
        )

    alias_count = conn.execute(
        "SELECT COUNT(*) AS alias_count FROM food_alias WHERE food_id = ?",
        (food_id,),
    ).fetchone()["alias_count"]

    if alias_count > 0:
        conn.close()
        return render_admin_page(
            request=request,
            user=user,
            query_filter=query_filter.strip(),
            category_filter=category_filter.strip(),
            selected_food_id=food_id,
            error="This food still has aliases. Remove them from the alias admin page before deleting the food.",
            status_code=400,
        )

    conn.execute("DELETE FROM food_master WHERE id = ?", (food_id,))
    conn.commit()
    conn.close()

    return RedirectResponse(
        url=build_admin_url(query_filter.strip(), category_filter.strip()),
        status_code=303,
    )