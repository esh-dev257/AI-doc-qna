from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Document & Multimedia Q&A"
    environment: str = "development"
    debug: bool = True

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "ai_qa"

    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    openai_transcribe_model: str = "whisper-1"

    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    gemini_transcribe_model: str = "gemini-2.5-flash"

    llm_provider: str = "auto"  # "auto" | "gemini" | "openai" | "offline"

    upload_dir: str = "./uploads"
    max_upload_mb: int = 200

    rate_limit_per_minute: int = 60
    cors_origins: str = "*"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
