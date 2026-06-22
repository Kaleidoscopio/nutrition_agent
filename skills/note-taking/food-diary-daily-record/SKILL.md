---
name: food-diary-daily-record
description: Maintain one canonical daily food diary record in the local JSON store, recover same-day context when needed, and mirror cautiously to fact_store only when explicitly required.
---

# When to use
Use when the user logs a meal, corrects an earlier food entry, asks for the current daily total, or wants the same day's diary carried forward across sessions.

# Goal
Keep exactly one canonical daily record per date under `~/.hermes/data/food-diary/entries/YYYY-MM-DD.json`.

Treat the local canonical JSON record as the source of truth for day-level diary state. Use `fact_store` only for optional mirroring, older historical backfill, or aggregate analysis.

# Required structure
Each daily record should contain at least:
- `date`
- `status` (`partial` or `complete`)
- `user`
- `source_of_truth` = `local-canonical`
- `meals.breakfast|lunch|dinner|snacks` arrays (`description`, `estimated_kcal`, `quantity`, `estimated` [true or false])
- `totals.breakfast_kcal|lunch_kcal|dinner_kcal|snacks_kcal|daily_kcal`
- `fact_store.canonical_fact_id`
- `fact_store.last_known_sync_status` (`verified` or `pending`)
- `notes`

# Core rules
1. Keep one canonical day record per date. Do not create competing partial summaries.
2. Read the existing local file before updating it.
3. Treat incremental changes as merge operations unless the user is clearly correcting or replacing an earlier item.
4. Preserve existing meal arrays that are unrelated to the current update.
5. Use `session_search` when the local record looks incomplete or when same-day context may exist outside the current turn.
6. Use `terminal` or `execute_code` for calorie arithmetic. Never do it in-head.
7. Only claim persistence that you actually verified.
8. Mirror to `fact_store` only when the task explicitly needs it and the write can be verified.

# Workflow
1. Resolve the target date with `terminal` when the user says `today`, `hoje`, `yesterday`, `ontem`, or similar.
2. Parse the new meal/correction request and identify the target meal slot.
3. Read `entries/YYYY-MM-DD.json` if it exists.
4. If the local record is missing, suspiciously incomplete, or likely stale for the same date, use `session_search` with an explicit date token to recover same-day meals before writing.
5. Merge the new meal items or corrections into the appropriate section:
   - add new items when the user is logging additional food
   - replace earlier estimates when the user provides better data
   - move items if the original date/meal slot was wrong
6. Recompute:
   - breakfast total
   - lunch total
   - dinner total
   - snacks total
   - daily total
7. Write the updated canonical day file.
8. If the task also requires a mirror summary in `fact_store`, write one canonical summary fact for the date and record the id/status explicitly.
9. Verify by reading back the local file.
10. Reply with the full fixed day structure:
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
- Do not claim `fact_store` is the source of truth for the current day when the local canonical file exists.
- Do not return only the newly added meal when the task implies the running daily total matters.
- Do not say something is saved if the write or readback was not actually verified.

# Verification
Before finishing:
- target entry file exists
- unrelated existing meals were preserved
- totals match the meal items
- any estimates are labeled
- any claimed `fact_store` mirror status is explicit and verified
