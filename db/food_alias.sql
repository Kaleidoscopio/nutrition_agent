CREATE TABLE food_alias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food_id INTEGER NOT NULL,
    alias TEXT NOT NULL,

    FOREIGN KEY(food_id)
        REFERENCES food_master(id),

    UNIQUE(alias)
);