import json
import os
from dotenv import load_dotenv

load_dotenv()


DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://map2drone:map2drone@localhost:5432/map2drone",
)

SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
REFRESH_TOKEN_EXPIRE_DAYS: int = 7

CORS_ORIGINS: list[str] = json.loads(
    os.getenv("CORS_ORIGINS", '["http://localhost:5173"]')
)

PROJECT_NAME: str = "Map2Drone"
VERSION: str = "0.1.0"
