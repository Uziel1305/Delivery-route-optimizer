from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery("route_optimizer", broker=settings.celery_broker_url)
celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)

# Import after celery_app is defined so @celery_app.task registration works.
import app.tasks.optimization_tasks  # noqa: E402,F401
