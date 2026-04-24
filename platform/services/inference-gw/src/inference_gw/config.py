from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    service_name: str = "inference-gw"
    service_port: int = 3003
    log_level:    str = "INFO"

    # LLM Provider API Keys
    nvidia_api_key:    str | None = None
    openai_api_key:    str | None = None
    anthropic_api_key: str | None = None
    google_api_key:    str | None = None
    ollama_base_url:   str = "http://localhost:11434"

    # 預設供應商（找不到對應 provider 時使用）
    inference_default_provider: str = "nvidia"

    # Tenant Service（用於配額查詢）
    tenant_service_url: str = "http://localhost:3001"


settings = Settings()
