"""The health check (S-5): ready only when the database answers and the
worker has loaded the chosen model."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from chama.web.db import engine

router = APIRouter(prefix="/api")

WORKER_SILENT_AFTER = timedelta(seconds=60)


def health_report() -> tuple[bool, dict]:
    parts = {"database": "not answering", "worker": "not running", "model": "not loaded"}
    try:
        with engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            parts["database"] = "ready"
            worker = conn.execute(text(
                "SELECT model_run_id, model_loaded_at, last_seen_at FROM app.worker_status "
                "ORDER BY last_seen_at DESC LIMIT 1")).first()
    except Exception:  # noqa: BLE001 - any failure means not ready
        return False, parts
    if worker and datetime.now(timezone.utc) - worker.last_seen_at < WORKER_SILENT_AFTER:
        parts["worker"] = "ready"
        if worker.model_loaded_at:
            parts["model"] = f"ready (run {worker.model_run_id[:8]})"
    ready = all(v.startswith("ready") for v in parts.values())
    return ready, parts


@router.get("/health")
def health() -> JSONResponse:
    ready, parts = health_report()
    return JSONResponse({"status": "ready" if ready else "not ready", "parts": parts},
                        status_code=200 if ready else 503)
