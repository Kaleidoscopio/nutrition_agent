# Body metrics canonical store

This directory stores one canonical JSON record per date for Daniel Almeida's:
- weight
- BMI
- muscle mass
- steps
- training/activity
- derived calorie estimates when available

Layout:
- index.json
- entries/YYYY-MM-DD.json

Conventions:
- one canonical record per date
- `status` is `partial` until the day is closed or data is complete enough
- keep unknown values as null instead of inventing them
