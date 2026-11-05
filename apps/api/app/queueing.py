from collections.abc import Sequence
from typing import Any

from fastapi import BackgroundTasks

from app.celery_app import celery_app


def enqueue(task: Any, args: Sequence[Any], background: BackgroundTasks) -> None:
    """Starts a job and returns at once.

    Without Redis, jobs run inline. Doing that during the request would keep the page waiting a minute or
    two with no way to show progress, so they run just after the response instead.
    """
    if celery_app.conf.task_always_eager:
        background.add_task(task.apply, args=list(args))
    else:
        task.apply_async(args=list(args), retry=False)
