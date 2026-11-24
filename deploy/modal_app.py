"""The public demo's API on Modal (https://modal.com), within its free monthly credits.

One container runs the API and does the AI work right after each request (CELERY_TASK_ALWAYS_EAGER), so
there is no Redis or Celery worker. The AI model is reached through OpenRouter. The container starts on
the first request and stops after SCALEDOWN_SECONDS without any, so an idle demo costs nothing.
Scheduled jobs that Celery beat runs on a full server run here as Modal cron functions.

Settings come from the Modal secret "careerfit-demo" (docs/deployment.md lists them).
Deploy: modal deploy deploy/modal_app.py
"""

import os
import sys
from pathlib import Path
from typing import Any

import modal

API_DIR = Path(__file__).resolve().parents[1] / "apps" / "api"
SCALEDOWN_SECONDS = 300

image = modal.Image.from_dockerfile(API_DIR / "Dockerfile", context_dir=API_DIR)
secrets = [modal.Secret.from_name("careerfit-demo")]
app = modal.App("careerfit-demo")


def _use_api_code() -> None:
    # The image keeps the API in /app; Modal starts functions elsewhere.
    os.chdir("/app")
    if "/app" not in sys.path:
        sys.path.insert(0, "/app")


@app.function(
    image=image,
    secrets=secrets,
    # Exactly one container, so rate limits counted in memory are complete (SINGLE_INSTANCE).
    max_containers=1,
    scaledown_window=SCALEDOWN_SECONDS,
    cpu=1.0,
    # The embedding model alone takes about 550 MB.
    memory=(1024, 2048),
    # A request plus the AI job that runs after it, which can take several minutes.
    timeout=1800,
)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def api() -> Any:
    _use_api_code()
    from app.main import app as fastapi_app

    return fastapi_app


@app.function(image=image, secrets=secrets, schedule=modal.Cron("30 3 * * *"), timeout=1800)
def nightly_cleanup() -> None:
    """Uploaded files past their 90 days, then demo accounts past DEMO_ACCOUNT_DAYS."""
    _use_api_code()
    from app import tasks

    tasks.delete_expired_files_task()
    tasks.delete_expired_demo_accounts_task()


@app.function(
    image=image, secrets=secrets, schedule=modal.Cron("0 6 * * 1"), timeout=3600, memory=2048
)
def weekly_market_refresh() -> None:
    """Job Bank publishes monthly on no fixed day, so this checks weekly. Re-running changes nothing."""
    _use_api_code()
    from app import tasks

    tasks.refresh_market_data_task()
