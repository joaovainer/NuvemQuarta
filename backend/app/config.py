from functools import lru_cache
from os import getenv
from pathlib import Path


class Settings:
    app_name = "Mural de Ideias Distribuido"
    database_url = getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mural")
    redis_url = getenv("REDIS_URL", "redis://localhost:6379/0")
    cache_ttl_seconds = int(getenv("CACHE_TTL_SECONDS", "10"))
    frontend_dir = Path(getenv("FRONTEND_DIR", "frontend")).resolve()

    @property
    def cors_origins(self) -> list[str]:
        raw_origins = getenv("CORS_ORIGINS", "*")
        return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
