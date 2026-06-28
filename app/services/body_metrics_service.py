def calculate_bmi(weight_kg: float | None, height_cm: float | None) -> float | None:
    if not weight_kg or not height_cm or height_cm <= 0:
        return None

    bmi = (weight_kg / (height_cm * height_cm)) * 10000
    return round(bmi, 1)