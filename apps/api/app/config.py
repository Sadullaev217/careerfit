from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "CareerFit API"
    app_version: str = "0.0.1"
    environment: str = "development"
    debug: bool = False

    # Supabase
    supabase_url: str = ""
    supabase_secret_key: str = ""
    storage_bucket: str = "documents"

    # Documents
    ocr_languages: str = "eng+rus"
    github_token: str = ""
    celery_task_always_eager: bool = False

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # AI
    llm_provider: str = "ollama"
    llm_model: str = "qwen3.5:4b"
    llm_timeout_seconds: float = 300
    ollama_url: str = "http://localhost:11434"

    # Push notifications. The token is only needed if push security is turned on at expo.dev.
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"
    expo_access_token: str = ""

    # Stripe. Payment pages send people back to the web app at web_url.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    web_url: str = "http://localhost:3000"

    # Sentry
    sentry_dsn: str = ""

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:8081"]


settings = Settings()
