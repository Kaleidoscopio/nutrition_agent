-- 1. EXPENDITURE & ACTIVITY SUMMARY
CREATE TABLE daily_expenditure (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    user_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('partial', 'complete', 'processed')),
    bmr_kcal INTEGER DEFAULT 0,       -- <--- NOVA COLUNA: Taxa Metabólica Basal
    activity_kcal INTEGER DEFAULT 0,  -- Calories burned via exercise/steps
    tdee_kcal INTEGER DEFAULT 0,      -- Total daily expenditure (BMR + activity_kcal)
    net_balance_kcal INTEGER DEFAULT 0, -- daily_kcal (from daily_meal) - tdee_kcal
    notes TEXT,
    CONSTRAINT uq_daily_expenditure UNIQUE(entry_date, user_name)
);

-- 2. EXERCISE DETAILS (Handles multiple exercises/steps per day)
CREATE TABLE log_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expenditure_id INTEGER NOT NULL,  -- Clear, fast FK linkage
    activity_type TEXT NOT NULL,      -- 'steps', 'strength', 'cardio', 'other'
    duration_minutes INTEGER,
    activity_value TEXT,               -- 'pesos', '10000 steps'
    FOREIGN KEY (expenditure_id) REFERENCES daily_expenditure (id) ON DELETE CASCADE
);

-- 3. BODY METRICS (Weight and composition tracking)
CREATE TABLE body_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    user_name TEXT NOT NULL,
    weight_kg REAL,
    bmi REAL,
    muscle_mass_pct REAL,
    body_fat_pct REAL,
    CONSTRAINT uq_body_metrics UNIQUE(entry_date, user_name)
);