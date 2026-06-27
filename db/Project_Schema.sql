USE food_diary;

-- 1. EXPENDITURE & ACTIVITY SUMMARY
CREATE TABLE "daily_expenditure" (
	"id"	INTEGER,
	"entry_date"	TEXT NOT NULL,
	"user_name"	TEXT NOT NULL,
	"status"	TEXT NOT NULL CHECK("status" IN ('partial', 'complete', 'processed')),
	"bmr_kcal"	INTEGER DEFAULT 0,
	"activity_kcal"	INTEGER DEFAULT 0,
	"tdee_kcal"	INTEGER DEFAULT 0,
	"net_balance_kcal"	INTEGER DEFAULT 0,
	"notes"	TEXT,
	CONSTRAINT "uq_daily_expenditure" UNIQUE("entry_date","user_name"),
	PRIMARY KEY("id" AUTOINCREMENT)
);

-- 2. EXERCISE DETAILS (Handles multiple exercises/steps per day)
CREATE TABLE "log_activities" (
	"id"	INTEGER,
	"expenditure_id"	INTEGER NOT NULL,
	"activity_type"	TEXT NOT NULL,
	"duration_minutes"	INTEGER,
	"activity_value"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("expenditure_id") REFERENCES "daily_expenditure"("id") ON DELETE CASCADE
);

-- 3. BODY METRICS (Weight and composition tracking)
CREATE TABLE "body_metrics" (
	"id"	INTEGER,
	"entry_date"	TEXT NOT NULL,
	"user_name"	TEXT NOT NULL,
	"weight_kg"	REAL,
	"bmi"	REAL,
	"muscle_mass_pct"	REAL,
	"body_fat_pct"	REAL,
	CONSTRAINT "uq_body_metrics" UNIQUE("entry_date","user_name"),
	PRIMARY KEY("id" AUTOINCREMENT)
);

CREATE TABLE "daily_meal" (
	"id"	INTEGER,
	"entry_date"	TEXT,
	"meal_status"	TEXT NOT NULL CHECK("meal_status" IN ('partial', 'complete', 'processed')),
	"user_name"	TEXT NOT NULL,
	"daily_kcal"	INTEGER,
	"notes"	TEXT,
	CONSTRAINT "uq_daily_meal" UNIQUE("entry_date","user_name"),
	PRIMARY KEY("id" AUTOINCREMENT)
);

CREATE TABLE "daily_meal_detail" (
	"id"	INTEGER,
	"created_at"	TEXT DEFAULT CURRENT_TIMESTAMP,
	"daily_meal_id"	INTEGER NOT NULL,
	"meal_type"	TEXT NOT NULL CHECK("meal_type" IN ('breakfast', 'lunch', 'dinner', 'snacks')),
	"food_id"	INTEGER NOT NULL,
	"quantity"	REAL(10, 2),
	"unit"	TEXT,
	"calories"	REAL(10, 2),
	"protein"	REAL(10, 2),
	"carbs"	REAL(10, 2),
	"fat"	REAL(10, 2),
	PRIMARY KEY("id" AUTOINCREMENT),
	CONSTRAINT "fk_meal" FOREIGN KEY("daily_meal_id") REFERENCES "daily_meal"("id")
);

CREATE TABLE "food_alias" (
	"id"	INTEGER,
	"food_id"	INTEGER NOT NULL,
	"alias"	TEXT NOT NULL,
	UNIQUE("alias"),
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("food_id") REFERENCES "food_master"("id")
);

CREATE TABLE "food_master" (
	"id"	INTEGER,
	"food_name"	TEXT NOT NULL,
	"search_text"	TEXT,
	"food_category"	TEXT,
	"calories_100g"	REAL,
	"protein_100g"	REAL,
	"carbs_100g"	REAL,
	"fat_100g"	REAL,
	"fiber_100g"	REAL,
	"sugar_100g"	REAL,
	"salt_100g"	REAL,
	"source"	TEXT NOT NULL,
	"source_food_id"	TEXT NOT NULL,
	"created_at"	TEXT DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("id" AUTOINCREMENT),
	UNIQUE("source","source_food_id")
);
	 
