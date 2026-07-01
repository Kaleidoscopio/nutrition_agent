from datetime import date


ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "very_active": 1.725,
    "extra_active": 1.9,
}


def calculate_age(date_of_birth) -> int | None:
    if not date_of_birth:
        return None

    if isinstance(date_of_birth, date):
        dob = date_of_birth
    else:
        try:
            dob = date.fromisoformat(date_of_birth)
        except (ValueError, TypeError):
            return None

    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def calculate_bmr(sex: str, age: int, height_cm: float, weight_kg: float) -> float | None:
    if not sex or age is None or not height_cm or not weight_kg:
        return None

    sex = sex.strip().lower()

    if sex == "male":
        return round((10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5, 1)

    if sex == "female":
        return round((10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161, 1)

    return None


def calculate_tdee(bmr: float, activity_level: str) -> float | None:
    factor = ACTIVITY_FACTORS.get((activity_level or "").strip().lower())
    if bmr is None or factor is None:
        return None
    return round(bmr * factor, 1)


def build_energy_summary(profile: dict, today_kcal: float) -> dict:
    age = calculate_age(profile.get("date_of_birth"))
    weight_kg = profile.get("weight_kg") or profile.get("start_weight_kg")
    bmr = calculate_bmr(profile.get("sex"), age, profile.get("height_cm"), weight_kg)
    tdee = calculate_tdee(bmr, profile.get("activity_level"))

    if tdee is None:
        return {
            "age": age,
            "bmr": None,
            "tdee": None,
            "net_balance": None,
            "status": None,
            "message": "Complete your profile to estimate maintenance calories.",
        }

    net_balance = round(today_kcal - tdee, 1)

    if net_balance > 50:
        status = "above"
        message = f"You are {abs(net_balance):.0f} kcal above maintenance today."
    elif net_balance < -50:
        status = "below"
        message = f"You are {abs(net_balance):.0f} kcal below maintenance today."
    else:
        status = "at"
        message = "You are roughly at maintenance today."

    return {
        "age": age,
        "bmr": bmr,
        "tdee": tdee,
        "net_balance": net_balance,
        "status": status,
        "message": message,
    }