from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    service_name: str = "sandbox"
    service_port: int = 3002
    log_level:    str = "INFO"

    postgres_host:     str = "localhost"
    postgres_port:     int = 5432
    postgres_user:     str = "nemoclaw"
    postgres_password: str = "changeme"
    postgres_db:       str = "nemoclaw"

    # "mock"      = MockAdapter（Windows/Unit Test，不需要任何外部依賴）
    # "k8s"       = K8sAdapter（Ubuntu Server，Namespace-per-Tenant 真正隔離）← 推薦
    # "openshell" = OpenShellAdapter（Ubuntu Server，openshell CLI，無真正 NS 隔離）
    # "nemoclaw"  = 同 openshell（舊名稱，相容性保留）
    sandbox_backend: str = "mock"

    # OpenShell Adapter 設定
    openshell_sandbox_image:    str      = "openclaw"   # community sandbox name
    openshell_gateway_endpoint: str | None = None       # 空則使用已儲存的 gateway

    # Tenant Service URL（用於配額查詢）
    tenant_service_url: str = "http://localhost:3001"

    @property
    def postgres_dsn(self) -> str:
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
