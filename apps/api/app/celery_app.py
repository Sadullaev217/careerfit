import logging
from typing import Any

from celery import Celery
from celery.schedules import crontab
from celery.signals import after_setup_logger, after_setup_task_logger

from app import privacy_logging
from app.config import settings

privacy_logging.init_error_reports()


@after_setup_logger.connect  # type: ignore[untyped-decorator]
@after_setup_task_logger.connect  # type: ignore[untyped-decorator]
def _keep_personal_data_out_of_worker_logs(
    logger: logging.Logger, *_args: Any, **_kwargs: Any
) -> None:
    for handler in logger.handlers:
        if not any(isinstance(f, privacy_logging.RedactingFilter) for f in handler.filters):
            handler.addFilter(privacy_logging.RedactingFilter())


celery_app = Celery(
    "careerfit",
    broker=settings.celery_broker_url,
    include=["app.tasks"],
)
celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_ignore_result=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"socket_connect_timeout": 3},
    task_serializer="json",
    accept_content=["json"],
    # Job Bank publishes monthly on no fixed day, so this checks weekly. Re-running changes nothing.
    beat_schedule={
        "refresh-market-data": {
            "task": "refresh_market_data",
            "schedule": crontab(day_of_week=1, hour=6, minute=0),
        }
    },
)
