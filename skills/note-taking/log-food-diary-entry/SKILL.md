---
name: log-food-diary-entry
description: Maintain one canonical daily food diary record in the local JSON store, recover same-day context when needed, and mirror cautiously to fact_store only when explicitly required.
---

# When to use
Use when the user logs a meal, corrects an earlier food entry, asks for the current daily total, or wants the same day's diary carried forward across sessions.

# Goal
Keep exactly one canonical daily record per date under `/home/droque/.hermes/data/food-diary/entries/YYYY-MM-DD.json`.

Treat the local canonical JSON record as the source of truth for day-level diary state.

# Required structure
You must output a JSON object representing the daily meal log. Follow this exact TypeScript structure:

type MealItem = {
  description: string;   // Brief description of the food/drink. Important: Encode in RAW UTF-8
  kcal: number;          // Total calories for this item
  estimated: boolean;    // true if calculated/estimated, false if exact/known
  assumption?: string;   // REQUIRED if estimated is true. Explain the calculation/logic.
  food_id?: number;      // Optional. Include only if matched with a database item.
  quantity?: string;     // Optional. e.g., "200 g", "150 ml".
};

interface DailyMealLog {
  date: string;          // Format: "YYYY-MM-DD"
  status: "partial" | "completed"; // REQUIRED. Use "partial" if the day is ongoing.
  user: string;          // e.g., "Daniel Almeida"
  source_of_truth: "local-canonical";
  meals: {
    breakfast: MealItem[];
    lunch: MealItem[];
    dinner: MealItem[];
    snacks: MealItem[];
  };
  totals: {
    breakfast_kcal: number; // Sum of breakfast items
    lunch_kcal: number;     // Sum of lunch items
    dinner_kcal: number;    // Sum of dinner items
    snacks_kcal: number;    // Sum of snacks items
    daily_kcal: number;     // Total sum of all meals
  };
  notes: string[];       // Array of strings summarizing data decisions (e.g., source of calories, assumptions made)
}

# Core rules
1. Keep one canonical day record per date. Do not create competing partial summaries.
2. Read the existing local file before updating it.
3. Treat incremental changes as merge operations unless the user is clearly correcting or replacing an earlier item.
4. Preserve existing meal arrays that are unrelated to the current update.
5. Use `session_search` when the local record looks incomplete or when same-day context may exist outside the current turn.
6. Use `terminal` or `execute_code` for calorie arithmetic. Never do it in-head.
7. Only claim persistence that you actually verified.
8. Mirror to `fact_store` only when the task explicitly needs it and the write can be verified.

# Food lookup policy
Before estimating calories for any food item, always search the local food database.

Search order:

1. Search the SQLite database:
   - Database:
     `/home/droque/.hermes/data/db/food_diary.db`
   - Table:
     `food_master`
   - Search column:
     `search_text`
   - Matching:
     Use fuzzy matching instead of exact string comparison.
     Accept spelling mistakes, accents, plural/singular, aliases, different word order and common abbreviations.

2. If a sufficiently confident match is found:
   - Use the database nutritional information.
   - Populate `food_id`.
   - Set `estimated` to `false`.
   - Do not perform an online search.

3. Only if no acceptable local match exists:
   - Search online.
   - Estimate calories if necessary.
   - Set `estimated=true`.
   - Populate `assumption`.

The local database is always considered the authoritative source whenever a suitable match exists.

## Fuzzy matching acceptance rules
A fuzzy match is considered acceptable when its confidence score is at least 90%.
Confidence interpretation:
- **≥90%**
  - Accept automatically.
  - Use the matched `food_id`.
  - Use the nutritional values from the database.
- **75–89%**
  - If only one candidate clearly stands out, accept it.
  - If multiple candidates are similarly likely, ask the user which one was intended.
- **<75%**
  - Treat as "not found".
  - Continue with online lookup.
When several candidates have similar confidence scores, never guess. Ask the user to clarify.

# Workflow
1. Resolve the target date with `terminal` when the user says `today`, `hoje`, `yesterday`, `ontem`, or similar.
2. Parse the meal.
3. Search the local food database using fuzzy matching for every food item.
4. Only perform online lookup for items that could not be matched locally.
5. Read `entries/YYYY-MM-DD.json` if it exists.
6. If the local record is missing, suspiciously incomplete, or likely stale for the same date, use `session_search` with an explicit date token to recover same-day meals before writing.
7. Merge the new meal items or corrections into the appropriate section:
   - add new items when the user is logging additional food
   - replace earlier estimates when the user provides better data
   - move items if the original date/meal slot was wrong
8. Recompute:
   - breakfast total
   - lunch total
   - dinner total
   - snacks total
   - daily total
9. Write the updated canonical day file.
10. Verify by reading back the local file.
11. Reply with the full fixed day structure:
   - Pequeno-almoço
   - Almoço
   - Jantar
   - Snacks
   - Total diário

# Query guidance
Use OR-heavy `session_search` queries. Start narrow with the explicit date, then broaden only if needed.

Examples:
- `2026-06-15 OR pequeno-almoço OR almoço OR jantar OR snacks`
- `2026-06-15 OR diário alimentar OR total diário`
- `2026-06-15 OR snack OR lanche OR banana OR iogurte`

# Correction rules
- If the user corrects quantity/calories for an existing logged item, replace the old value instead of adding a duplicate.
- If the user later provides a package label or restaurant nutrition value, replace the estimate and recalculate the whole day.
- If an item was logged under the wrong date or meal, move it instead of duplicating it.
- If a mixed dish estimate is uncertain, record the assumption plainly.

# Partial vs complete
- `partial` means the day may still change.
- `complete` should only be used when the day is clearly closed.
- Do not silently convert a partial day to complete without enough evidence.
- If the user has a known habit of not eating after dinner, that can support closing a no-snacks-after-dinner day, but don't overreach.

# Pitfalls
- Do not overwrite the day from scratch without reading the existing file.
- Do not initialize missing meal arrays blindly if you have not checked whether earlier meals existed.
- Do not create multiple local files for the same date.
- Do not return only the newly added meal when the task implies the running daily total matters.
- Do not say something is saved if the write or readback was not actually verified.

# Verification
Before finishing:
- target entry file exists
- unrelated existing meals were preserved
- totals match the meal items
- any estimates are labeled
