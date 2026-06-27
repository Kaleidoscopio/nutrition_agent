import bcrypt

def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError("Password must be 72 bytes or fewer when using bcrypt.")

    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain_password_bytes = plain_password.encode("utf-8")

    if len(plain_password_bytes) > 72:
        return False

    return bcrypt.checkpw(
        plain_password_bytes,
        hashed_password.encode("utf-8")
    )