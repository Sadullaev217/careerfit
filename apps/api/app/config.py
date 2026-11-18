from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Servers that real people use. Each refuses to start with settings that are only safe on a laptop.
DEPLOYED_ENVIRONMENTS = frozenset({"staging", "production"})


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
    # How long reading a resume or scoring it may take in all. A slow CPU-only server needs more.
    ai_task_time_limit_seconds: int = 600
    ollama_url: str = "http://localhost:11434"
    # LLM_PROVIDER=openrouter sends resume text to a hosted model instead (see docs/ai-providers.md).
    openrouter_api_key: str = ""
    openrouter_model: str = "baidu/ernie-5.5-flash-preview:free"
    openrouter_url: str = "https://openrouter.ai/api/v1"
    # Use the local model when the hosted one fails, for example after its daily free limit.
    ollama_fallback: bool = True

    # Push notifications. The token is only needed if push security is turned on at expo.dev.
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"
    expo_access_token: str = ""

    # Stripe. Payment pages send people back to the web app at web_url.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    web_url: str = "http://localhost:3000"

    # RevenueCat (phone purchases). The secret key stays on the server; the app has its own public key.
    revenuecat_secret_key: str = ""

    # Sentry
    sentry_dsn: str = ""

    # PostHog product analytics (app/analytics.py). The project token is public; events carry no resume text.
    posthog_project_token: str = ""
    posthog_host: str = "https://eu.i.posthog.com"

    # AI spending alerts (app/llm_costs.py), in US dollars per day.
    llm_daily_budget_usd: float = 5.0
    llm_user_daily_budget_usd: float = 0.5

    # CORS: the exact web addresses allowed to call the API from a browser. The phone app isn't a browser.
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:8081"]

    # Virus scanning of uploads (app/malware_scan.py): "off" or "clamav". Deployed servers need clamav.
    malware_scanner: str = "off"
    clamav_host: str = "localhost"
    clamav_port: int = 3310

    # Request limits (app/rate_limit.py). Deployed servers keep counts in Redis, shared by every process.
    rate_limit_storage: str = "memory://"
    rate_limits_enabled: bool = True

    @property
    def deployed(self) -> bool:
        return self.environment in DEPLOYED_ENVIRONMENTS

    @model_validator(mode="after")
    def _safe_for_environment(self) -> Self:
        if "*" in self.allowed_origins:
            raise ValueError("ALLOWED_ORIGINS must list exact addresses, not *")
        if not self.deployed:
            return self
        problems = []
        if self.debug:
            problems.append("DEBUG must be off")
        if not self.supabase_url.startswith("https://") or not self.supabase_secret_key:
            problems.append("SUPABASE_URL must be https and SUPABASE_SECRET_KEY set")
        if not self.web_url.startswith("https://"):
            problems.append("WEB_URL must be https")
        if not self.allowed_origins or any(not o.startswith("https://") for o in self.allowed_origins):
            problems.append("ALLOWED_ORIGINS must be https addresses")
        if not self.rate_limit_storage.startswith(("redis://", "rediss://")):
            problems.append("RATE_LIMIT_STORAGE must point at Redis, so every process shares the counts")
        if self.malware_scanner != "clamav":
            problems.append("MALWARE_SCANNER must be clamav")
        if not self.rate_limits_enabled:
            problems.append("RATE_LIMITS_ENABLED must be on")
        if self.llm_provider == "demo":
            problems.append("LLM_PROVIDER=demo gives fixed answers and is for tests only")
        if self.llm_provider == "openrouter" and (
            not self.openrouter_api_key or not self.openrouter_url.startswith("https://")
        ):
            problems.append("OPENROUTER_API_KEY must be set and OPENROUTER_URL https")
        if problems:
            raise ValueError(f"Unsafe settings for {self.environment}: " + "; ".join(problems))
        return self


settings = Settings()
