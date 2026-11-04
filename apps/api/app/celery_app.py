from celery import Celery

from app.config import settings

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
)
