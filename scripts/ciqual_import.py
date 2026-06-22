import sqlite3
import pandas as pd             #   Requires: openpyxl
#import unicodedata
import re

DB_FILE = "food_diary.db"
EXCEL_FILE = "Table Ciqual 2025_ENG_2025_11_03.xlsx"

SOURCE = "ciqual"

def normalize_text(text):
    if text is None:
        return ""

    text = str(text).strip().lower()

    text = re.sub(r"[(),;:/]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def safe_float(value):
    if pd.isna(value):
        return None

    if isinstance(value, str):
        value = value.replace(",", ".")

    try:
        return float(value)
    except:
        return None


conn = sqlite3.connect(DB_FILE)

conn.execute("PRAGMA foreign_keys = ON")

cur = conn.cursor()

df = pd.read_excel(
    EXCEL_FILE,
    sheet_name="food composition"
)

for _, row in df.iterrows():

    food_name = row["alim_nom_eng"]

    search_text = normalize_text(food_name)

    food_category = row["alim_ssgrp_nom_eng"]

    source_food_id = str(row["alim_code"])

    calories = safe_float(
        row["Energy,\nRegulation\nEU No\n1169\n2011 (kcal\n100g)"]
    )

    protein = safe_float(
        row["Protein\n(g\n100g)"]
    )

    carbs = safe_float(
        row["Carbohydrate\n(g\n100g)"]
    )

    fat = safe_float(
        row["Fat (g\n100g)"]
    )

    fiber = safe_float(
        row["Fibres\n(g\n100g)"]
    )

    sugar = safe_float(
        row["Sugars\n(g\n100g)"]
    )

    salt = safe_float(
        row["Salt (g\n100g)"]
    )

    cur.execute("""
        INSERT OR IGNORE INTO food_master (
            source,
            source_food_id,
            food_name,
            search_text,
            food_category,
            calories_100g,
            protein_100g,
            carbs_100g,
            fat_100g,
            fiber_100g,
            sugar_100g,
            salt_100g
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, (
        SOURCE,
        source_food_id,
        food_name,
        search_text,
        food_category,
        calories,
        protein,
        carbs,
        fat,
        fiber,
        sugar,
        salt
    ))

'''
    cur.execute("""
        SELECT id
        FROM food_master
        WHERE source = ?
        AND source_food_id = ?
    """, (
        SOURCE,
        source_food_id
    ))

    food_id = cur.fetchone()[0]

    aliases = set()

    aliases.add(
        normalize_text(food_name)
    )

    for word in normalize_text(food_name).split():
        if len(word) > 3:
            aliases.add(word)

    for alias in aliases:

        cur.execute("""
            INSERT OR IGNORE INTO food_alias (
                food_id,
                alias
            )
            VALUES (?, ?)
        """, (
            food_id,
            alias
        ))
'''

conn.commit()

print(
    f"Imported {len(df)} foods from CIQUAL"
)

conn.close()