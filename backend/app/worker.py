import logging
import re
import threading
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any

from redis.exceptions import RedisError

from .cache import DASHBOARD_CACHE_KEY, IDEA_QUEUE, WORKER_HEARTBEAT_KEY, get_redis
from .db import fail_idea, finish_idea, get_idea, init_db, update_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

stop_event = threading.Event()
state: dict[str, Any] = {
    "started_at": None,
    "processed": 0,
    "last_job_id": None,
    "last_error": None,
}


def normalize_text(text: str) -> str:
    without_accents = unicodedata.normalize("NFKD", text)
    ascii_text = without_accents.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()


def analyze_idea(idea: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    text = normalize_text(f"{idea['title']} {idea['description']}")
    rules = {
        "Educacao": ["aula", "curso", "educacao", "ensino", "aprendizado"],
        "Sustentabilidade": ["energia", "horta", "reciclagem", "ambiental", "sustentabilidade"],
        "Comunidade": ["comunidade", "coletiva", "social", "integracao", "bairro"],
        "Operacao": ["fila", "atendimento", "processo", "monitorar", "tempo real"],
        "Baixo custo": ["simples", "baixo custo", "reduzir custos", "digital"],
    }
    tags = [tag for tag, words in rules.items() if any(word in text for word in words)]
    if not tags:
        tags = ["Geral"]

    word_count = len(re.findall(r"\w+", idea["description"]))
    score = min(100, 45 + (len(tags) * 10) + min(word_count, 25))
    analysis = {
        "resumo": f"Ideia com foco em {', '.join(tags[:2])}. Pode ser evoluida de forma incremental.",
        "pontuacao": score,
        "criterios": [
            "processada de forma assincrona pelo worker",
            "persistida no PostgreSQL",
            "disponibilizada para a API apos atualizacao do status",
        ],
    }
    return tags, analysis


def wait_for_database() -> None:
    while not stop_event.is_set():
        try:
            init_db()
            return
        except Exception as exc:
            state["last_error"] = f"Banco indisponivel: {exc}"
            logging.warning("Banco indisponivel, tentando novamente em 3s: %s", exc)
            time.sleep(3)


def process_job(job_id: int) -> None:
    idea = get_idea(job_id)
    if not idea:
        logging.warning("Ideia %s nao encontrada, ignorando job.", job_id)
        return

    update_status(job_id, "processing")
    get_redis().delete(DASHBOARD_CACHE_KEY)
    time.sleep(1.2)

    tags, analysis = analyze_idea(idea)
    finish_idea(job_id, tags, analysis)
    get_redis().delete(DASHBOARD_CACHE_KEY)

    state["processed"] += 1
    state["last_job_id"] = job_id
    state["last_error"] = None
    logging.info("Ideia %s processada com tags %s.", job_id, tags)


def run_worker() -> None:
    state["started_at"] = datetime.now(timezone.utc).isoformat()
    wait_for_database()
    redis_client = get_redis()

    while not stop_event.is_set():
        raw_job_id = None
        try:
            redis_client.set(WORKER_HEARTBEAT_KEY, datetime.now(timezone.utc).isoformat(), ex=60)
            job = redis_client.blpop(IDEA_QUEUE, timeout=5)
            if not job:
                continue
            _, raw_job_id = job
            process_job(int(raw_job_id))
        except RedisError as exc:
            state["last_error"] = f"Redis indisponivel: {exc}"
            logging.warning("Redis indisponivel, tentando novamente em 3s: %s", exc)
            time.sleep(3)
        except Exception as exc:
            state["last_error"] = str(exc)
            logging.exception("Erro ao processar job.")
            try:
                if raw_job_id is not None:
                    fail_idea(int(raw_job_id), str(exc))
                    get_redis().delete(DASHBOARD_CACHE_KEY)
            except Exception:
                logging.exception("Nao foi possivel marcar a ideia como failed.")


def request_stop() -> None:
    stop_event.set()


def worker_state() -> dict[str, Any]:
    return dict(state)
