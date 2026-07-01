-- 1. EXPENDITURE & ACTIVITY SUMMARY
CREATE TABLE "daily_expenditure" (
	"id"	INTEGER GENERATED ALWAYS AS IDENTITY,
	"entry_date"	TEXT NOT NULL,
	"user_name"	TEXT NOT NULL,
	"status"	TEXT NOT NULL CHECK("status" IN ('partial', 'complete', 'processed')),
	"bmr_kcal"	INTEGER DEFAULT 0,
	"activity_kcal"	INTEGER DEFAULT 0,
	"tdee_kcal"	INTEGER DEFAULT 0,
	"net_balance_kcal"	INTEGER DEFAULT 0,
	"notes"	TEXT,
	CONSTRAINT "uq_daily_expenditure" UNIQUE("entry_date","user_name"),
	PRIMARY KEY("id")
);

-- 2. EXERCISE DETAILS (Handles multiple exercises/steps per day)
CREATE TABLE "log_activities" (
	"id"	INTEGER GENERATED ALWAYS AS IDENTITY,
	"expenditure_id"	INTEGER NOT NULL,
	"activity_type"	TEXT NOT NULL,
	"duration_minutes"	INTEGER,
	"activity_value"	TEXT,
	"activity_label"	TEXT,
	"intensity"	TEXT,
	"calories_burned"	INTEGER DEFAULT 0,
	"notes"	TEXT,
	PRIMARY KEY("id"),
	FOREIGN KEY("expenditure_id") REFERENCES "daily_expenditure"("id") ON DELETE CASCADE
);

-- 3. BODY METRICS (Weight and composition tracking)
CREATE TABLE "body_metrics" (
	"id"	INTEGER GENERATED ALWAYS AS IDENTITY,
	"entry_date"	TEXT NOT NULL,
	"user_name"	TEXT NOT NULL,
	"weight_kg"	REAL,
	"bmi"	REAL,
	"muscle_mass_pct"	REAL,
	"body_fat_pct"	REAL,
	CONSTRAINT "uq_body_metrics" UNIQUE("entry_date","user_name"),
	PRIMARY KEY("id")
);

CREATE TABLE "daily_meal" (
	"id"	INTEGER GENERATED ALWAYS AS IDENTITY,
	"entry_date"	TEXT,
	"meal_status"	TEXT NOT NULL CHECK("meal_status" IN ('partial', 'complete', 'processed')),
	"user_name"	TEXT NOT NULL,
	"daily_kcal"	INTEGER,
	"notes"	TEXT,
	CONSTRAINT "uq_daily_meal" UNIQUE("entry_date","user_name"),
	PRIMARY KEY("id")
);

CREATE TABLE "daily_meal_detail" (
	"id"	INTEGER GENERATED ALWAYS AS IDENTITY,
	"created_at"	TEXT DEFAULT CURRENT_TIMESTAMP,
	"daily_meal_id"	INTEGER NOT NULL,
	"meal_type"	TEXT NOT NULL CHECK("meal_type" IN ('breakfast', 'lunch', 'dinner', 'snacks')),
	"food_id"	INTEGER NOT NULL,
	"quantity"	NUMERIC(10, 2),
	"unit"	TEXT,
	"calories"	NUMERIC(10, 2),
	"protein"	NUMERIC(10, 2),
	"carbs"	NUMERIC(10, 2),
	"fat"	NUMERIC(10, 2),
	"food_label"	TEXT,
	PRIMARY KEY("id"),
	CONSTRAINT "fk_meal" FOREIGN KEY("daily_meal_id") REFERENCES "daily_meal"("id")
);

CREATE TABLE "food_alias" (
	"id"	INTEGER GENERATED ALWAYS AS IDENTITY,
	"food_id"	INTEGER NOT NULL,
	"alias"	TEXT NOT NULL,
	UNIQUE("alias"),
	PRIMARY KEY("id"),
	FOREIGN KEY("food_id") REFERENCES "food_master"("id")
);

CREATE TABLE "food_master" (
	"id"	INTEGER GENERATED ALWAYS AS IDENTITY,
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
	PRIMARY KEY("id"),
	UNIQUE("source","source_food_id")
);
	 
CREATE TABLE "users" (
	"id"	INTEGER GENERATED ALWAYS AS IDENTITY,
	"user_name"	TEXT NOT NULL UNIQUE,
	"email"	TEXT UNIQUE,
	"password_hash"	TEXT NOT NULL,
	"display_name"	TEXT,
	"is_active"	INTEGER NOT NULL DEFAULT 1,
	"created_at"	TEXT DEFAULT CURRENT_TIMESTAMP,
	"sex"	TEXT,
	"date_of_birth"	TEXT,
	"height_cm"	REAL,
	"start_weight_kg"	REAL,
	"activity_level"	TEXT NOT NULL CHECK("activity_level" IN ('sedentary', 'light', 'moderate', 'very_active', 'extra_active')),
	"must_change_password"	INTEGER NOT NULL DEFAULT 0,
	PRIMARY KEY("id")
);

CREATE TABLE "daily_water" (
    "id" INTEGER GENERATED ALWAYS AS IDENTITY,
    "entry_date" TEXT NOT NULL,
    "user_name" TEXT NOT NULL,
    "target_ml" INTEGER NOT NULL DEFAULT 2000,
    "consumed_ml" INTEGER NOT NULL DEFAULT 0,
    "notes" TEXT,
    CONSTRAINT "uq_daily_water" UNIQUE("entry_date", "user_name"),
    PRIMARY KEY("id")
);

--	Create user admin with password "admin"
INSERT INTO "users"
	("user_name", "password_hash", "display_name", "activity_level", "must_change_password")
	VALUES ('admin', '$2b$12$xPlz4jkJNo79sFRmnxxSQePuyDxEMaUKb5AYmSRQe8340QcxJxQjy', 'admin', 'light', 1);