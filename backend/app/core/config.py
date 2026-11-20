from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import json

# Project root (backend directory)
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_FILE = (BACKEND_DIR / "fogguard.db").resolve()
# Use forward slashes for SQLite URI even on Windows
DEFAULT_DB_URI = f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str = DEFAULT_DB_URI
    CORS_ORIGINS: str = '["http://localhost:5173","http://127.0.0.1:5173","http://localhost:3000","http://127.0.0.1:3000"]'
    SIMULATION_MODE: bool = True
    SIMULATION_INTERVAL_MS: int = 100
    DATA_RETENTION_DAYS: int = 30
    MAX_RANGE_CM: float = 400.0
    CRITICAL_THRESHOLD_CM: float = 5.0
    WARNING_THRESHOLD_CM: float = 10.0
    CAUTION_THRESHOLD_CM: float = 15.0

    @property
    def cors_origins_list(self) -> List[str]:
        try:
            origins = json.loads(self.CORS_ORIGINS)
            if isinstance(origins, list):
                return origins
            return [str(origins)]
        except Exception:
            return [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ]


settings = Settings()
