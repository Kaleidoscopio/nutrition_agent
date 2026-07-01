import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "Food Diary")
    session_secret_key: str = os.getenv("SESSION_SECRET_KEY", "change-me")
    default_remember_days: int = int(os.getenv("DEFAULT_REMEMBER_DAYS", "30"))
    database_url: str = os.getenv("DATABASE_URL", "")

    def __post_init__(self):
        if not self.database_url:
            raise RuntimeError(
                "DATABASE_URL is not set. Add it to your .env file, e.g.\n"
                "DATABASE_URL=postgresql://user:password@host:5432/dbname"
            )


settings = Settings()