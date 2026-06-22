USE food_diary;

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


	 
