import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "Food Diary")
    session_secret_key: str = os.getenv("SESSION_SECRET_KEY", "change-me")
    default_remember_days: int = int(os.getenv("DEFAULT_REMEMBER_DAYS", "30"))


settings = Settings()