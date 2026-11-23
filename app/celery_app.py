import os
import ssl

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError(
        "REDIS_URL is not set. Use the Upstash Redis URL "
        "(rediss://default:...@....upstash.io:6379), not the REST https URL."
    )

celery_app = Celery(
    "sentinel",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["agent.ingestion.tasks"],
)

celery_app.conf.update(
    broker_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED},
    redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED},
    result_expires=3600,
    timezone="UTC",
    beat_schedule={
        "news-monitor-cycle": {
            "task": "agent.ingestion.tasks.run_news_monitor",
            "schedule": float(os.getenv("NEWS_POLL_INTERVAL_MINUTES", "15")) * 60.0,
        }
    },
)
