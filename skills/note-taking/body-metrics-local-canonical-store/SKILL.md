---
name: body-metrics-local-canonical-store
description: Maintain a local canonical JSON store for daily body metrics and activity under `/home/droque/.hermes/data/body-metrics/`.
---

# When to use
Use when the user logs daily body metrics or activity incrementally, especially in short messages like `ONTEM: peso 104,4; passos 8454; caminhada leve`.

# Goal
Keep one canonical local JSON record per date under `/home/droque/.hermes/data/body-metrics/entries/YYYY-MM-DD.json`.

Treat the local file as the source of truth for:
- weight
- BMI
- muscle mass
- body fat percentage
- steps
- training/activity
- derived calorie estimates when available

# Directory layout
- `/home/droque/.hermes/data/body-metrics/entries/YYYY-MM-DD.json`
- optional `README.md`

# Record shape
The agent MUST adhere exactly to the following JSON structure.
{
  "date": "YYYY-MM-DD",
  "status": "partial", 
  "user": "Daniel Almeida",
  "source_of_truth": "local-canonical",
  "measurements": {
    "weight_kg": null,
    "bmi": null,
    "muscle_mass_pct": null,
    "body_fat_pct": null
  },
  "activity": {
    "steps": null,
    "strength_training_minutes": null,
    "cardio_minutes": null,
    "other_activity": []
  },
  "estimates": {
    "activity_kcal": null
  },
  "notes": []
}

# Workflow
1. Use `terminal` to resolve relative dates like `ONTEM` against the live system date. Do not do date math in-head.
2. Create or update `entries/YYYY-MM-DD.json` for the target date.
3. Keep unknown values as `null` instead of inventing them.
4. Put free-text context such as `caminhada leve` into `activity.other_activity` and/or `notes`.
5. If the user later corrects a field for the same date, overwrite the canonical record for that date instead of appending a second record.
6. Verify by reading back both the entry file.

# Parsing guidance
Array Enforcement: * activity.other_activity must always be an array of strings (e.g., ["pesos"], ["caminhada leve"]). If there are no other activities, initialize it as an empty array []. NEVER set this key to null.
notes must always be an array of strings (e.g., ["Passos atualizados." ]). If empty, initialize it as []. NEVER set this key to null.
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

Calculating `estimates.activity_kcal` (DO NOT INVENT, USE FORMULAS):
If the user does not explicitly state the calories burned, you must calculate an estimate by summing the following base rules:
- **Steps:** (Total steps / 1000) * 40 kcal (e.g., 5000 steps = 200 kcal).
- **Strength Training:** minutes * 5 kcal.
- **Cardio / Other Activity:** minutes * 8 kcal (if duration is mentioned). 
Sum all applicable values. If no physical activity metrics are provided, set `activity_kcal` to `null`.

# Pitfalls
- Do not do date arithmetic mentally.
- Do not create multiple files for the same date.
- Do not mark missing metrics as zero; use `null`.
- Do not invent random calorie values; stick to the provided math formulas.

# Verification
Before finishing:
- target entry file exists
- supplied fields were written correctly
- omitted fields remain `null`
- ambiguous muscle-mass units are called out explicitly to the user
