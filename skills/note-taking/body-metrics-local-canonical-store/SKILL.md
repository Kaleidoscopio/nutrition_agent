---
name: body-metrics-local-canonical-store
description: Maintain a local canonical JSON store for daily body metrics and activity under ~/.hermes/data/body-metrics/.
---

# When to use
Use when the user logs daily body metrics or activity incrementally, especially in short messages like `ONTEM: peso 104,4; passos 8454; caminhada leve`.

# Goal
Keep one canonical local JSON record per date under `~/.hermes/data/body-metrics/entries/YYYY-MM-DD.json`.

Treat the local file as the source of truth for:
- weight
- BMI
- muscle mass
- body fat percentage
- steps
- training/activity
- derived calorie estimates when available

# Directory layout
- `~/.hermes/data/body-metrics/entries/YYYY-MM-DD.json`
- optional `README.md`

# Record shape
Use JSON with at least:
- `date`
- `status` (`partial` or `complete`)
- `user`
- `source_of_truth` = `local-canonical`
- `measurements.weight_kg|bmi|muscle_mass_kg|muscle_mass_pct|body_fat_pct`
- `activity.steps|strength_training_minutes|cardio_minutes|other_activity`
- `estimates.activity_kcal|tdee_kcal|net_balance_kcal`
- `notes`

If muscle mass is reported as a percentage rather than kilograms, do **not** silently coerce it into `muscle_mass_kg`; store it explicitly in `muscle_mass_pct`. Likewise, store scale-reported body fat in `body_fat_pct` when provided.

# Workflow
1. Use `terminal` to resolve relative dates like `ONTEM` against the live system date. Do not do date math in-head.
2. Create or update `entries/YYYY-MM-DD.json` for the target date.
3. Keep unknown values as `null` instead of inventing them.
4. Put free-text context such as `caminhada leve` into `activity.other_activity` and/or `notes`.
5. If the user later corrects a field for the same date, overwrite the canonical record for that date instead of appending a second record.
6. Verify by reading back both the entry file.

# Parsing guidance
Common compact inputs:
- `Hoje: peso 104,4; bmi 38,3; massa muscular 29%; passos 3120; treino força 45 min; cardio 0`
- `ONTEM: peso 104,4; bmi 38,1; massa muscular 29; passos 8454; treino força 0 min; cardio 0; notas caminhada leve`
- `Dia 06.06 Peso 104.6; Passos 4421; Caminhada leve`

Interpretation rules:
- `Hoje` = current system date
- `ONTEM` = current system date minus one day
- `Dia 06.06` needs year inference from current context; use the current year unless the user says otherwise
- decimal commas are normal; store normalized JSON numbers
- if units are omitted, only infer the obvious ones (`peso` in kg, `passos` as count, training/cardio in minutes)
- do not assume whether `massa muscular 29` means kg or percent; note ambiguity and let the user confirm

# Pitfalls
- Do not do date arithmetic mentally.
- Do not create multiple files for the same date.
- Do not convert ambiguous muscle-mass values into kilograms just because the field name exists.
- Do not mark missing metrics as zero; use `null`.
- Do not pretend the record is complete when only weight and steps were supplied.

# Verification
Before finishing:
- target entry file exists
- supplied fields were written correctly
- omitted fields remain `null`
- ambiguous muscle-mass units are called out explicitly to the user
