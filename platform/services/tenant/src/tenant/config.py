from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py is at services/tenant/src/tenant/
# parents[4] goes up to platform/
# config.py -> tenant/ -> src/ -> services/tenant/ -> services/ -> platform/
_ENV_FILE = Path(__file__).parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        extra="ignore",
    )

    service_name: str = "tenant"
    service_port: int = 3001
    log_level: str = "INFO"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "nemoclaw"
    postgres_password: str = "changeme"
    postgres_db: str = "nemoclaw"

    redis_url: str = "redis://localhost:6379/0"

    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "nemoclaw"

    @property
    def postgres_dsn(self) -> str:
        # quote_plus 將特殊字元（@、#、!、空格等）轉為 URL 安全格式
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
