import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from .cache import DASHBOARD_CACHE_KEY, IDEA_QUEUE, WORKER_HEARTBEAT_KEY, get_redis, invalidate_dashboard_cache
from .config import get_settings
from .db import create_idea, database_ping, idea_counts_by_status, init_db, list_ideas


class IdeaInput(BaseModel):
    author: str = Field(..., min_length=2, max_length=60, examples=["Ana"])
    title: str = Field(..., min_length=3, max_length=90, examples=["Horta comunitaria"])
    description: str = Field(
        ...,
        min_length=10,
        max_length=600,
        examples=["Criar uma horta para aproximar a comunidade e reduzir desperdicio."],
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_dashboard_payload() -> dict[str, Any]:
    redis_client = get_redis()
    return {
        "ideas": list_ideas(),
        "stats": {
            "statuses": idea_counts_by_status(),
            "queue_size": redis_client.llen(IDEA_QUEUE),
            "worker_last_heartbeat": redis_client.get(WORKER_HEARTBEAT_KEY),
        },
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    status = {
        "service": "api",
        "database": "unknown",
        "redis": "unknown",
        "queue_size": None,
        "worker_last_heartbeat": None,
    }

    try:
        database_ping()
        status["database"] = "ok"
    except Exception as exc:
        status["database"] = f"error: {exc}"

    try:
        redis_client = get_redis()
        redis_client.ping()
        status["redis"] = "ok"
        status["queue_size"] = redis_client.llen(IDEA_QUEUE)
        status["worker_last_heartbeat"] = redis_client.get(WORKER_HEARTBEAT_KEY)
    except RedisError as exc:
        status["redis"] = f"error: {exc}"

    status["status"] = "ok" if status["database"] == "ok" and status["redis"] == "ok" else "degraded"
    return status


@app.get("/api/ideas")
def ideas() -> dict[str, Any]:
    redis_client = get_redis()
    cached_payload = redis_client.get(DASHBOARD_CACHE_KEY)
    if cached_payload:
        return json.loads(cached_payload)

    payload = build_dashboard_payload()
    redis_client.setex(DASHBOARD_CACHE_KEY, settings.cache_ttl_seconds, json.dumps(payload))
    return payload


@app.post("/api/ideas", status_code=201)
def submit_idea(payload: IdeaInput) -> dict[str, Any]:
    idea = create_idea(payload.author.strip(), payload.title.strip(), payload.description.strip())
    try:
        get_redis().rpush(IDEA_QUEUE, idea["id"])
        invalidate_dashboard_cache()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail=f"Ideia salva, mas a fila Redis falhou: {exc}") from exc
    return {"message": "Ideia recebida e enviada para processamento distribuido.", "idea": idea}


@app.post("/api/demo")
def seed_demo() -> dict[str, Any]:
    samples = [
        (
            "Ana",
            "Horta comunitaria",
            "Criar uma horta coletiva para educacao ambiental, alimentos frescos e integracao social.",
        ),
        (
            "Bruno",
            "Painel de energia",
            "Monitorar consumo de energia em tempo real para reduzir custos e incentivar sustentabilidade.",
        ),
        (
            "Carla",
            "Fila inteligente",
            "Organizar atendimentos com uma fila digital para diminuir espera e melhorar a experiencia.",
        ),
    ]
    created = [create_idea(author, title, description) for author, title, description in samples]
    redis_client = get_redis()
    for idea in created:
        redis_client.rpush(IDEA_QUEUE, idea["id"])
    invalidate_dashboard_cache()
    return {"created": len(created), "ideas": created}


frontend_dir = settings.frontend_dir
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    @app.get("/")
    def missing_frontend() -> JSONResponse:
        return JSONResponse({"message": "Frontend nao encontrado. Use /api/health para testar a API."})
