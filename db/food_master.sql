CREATE TABLE food_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    food_name TEXT NOT NULL,
    food_category TEXT,

    calories_100g REAL,
    protein_100g REAL,
    carbs_100g REAL,
    fat_100g REAL,
    fiber_100g REAL,
    sugar_100g REAL,
    salt_100g REAL,

    source TEXT NOT NULL,
    source_food_id TEXT NOT NULL,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(source, source_food_id)
);