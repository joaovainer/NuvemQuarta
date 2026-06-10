from functools import lru_cache

from redis import Redis

from .config import get_settings


IDEA_QUEUE = "idea-jobs"
DASHBOARD_CACHE_KEY = "dashboard:ideas:v1"
WORKER_HEARTBEAT_KEY = "worker:last-heartbeat"


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def invalidate_dashboard_cache() -> None:
    get_redis().delete(DASHBOARD_CACHE_KEY)
