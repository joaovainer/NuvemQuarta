import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from .cache import IDEA_QUEUE, WORKER_HEARTBEAT_KEY, get_redis
from .worker import request_stop, run_worker, worker_state


@asynccontextmanager
async def lifespan(_: FastAPI):
    thread = threading.Thread(target=run_worker, name="idea-worker", daemon=True)
    thread.start()
    yield
    request_stop()
    thread.join(timeout=5)


app = FastAPI(title="Mural Worker", version="1.0.0", lifespan=lifespan)


@app.get("/")
@app.get("/health")
def health() -> dict[str, Any]:
    redis_client = get_redis()
    return {
        "service": "worker",
        "status": "ok",
        "queue_size": redis_client.llen(IDEA_QUEUE),
        "heartbeat": redis_client.get(WORKER_HEARTBEAT_KEY),
        "worker": worker_state(),
    }
