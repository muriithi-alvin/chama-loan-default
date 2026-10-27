"""The FastAPI app: the JSON API under /api/ that the pages in frontend/ call.

Run it with:  uvicorn chama.web.app:app --port 8000
The Next.js server forwards every /api/ request here, so the browser sees one
site and the session cookie stays first-party.

Middleware, outermost first:
- refuses a change (POST, PUT, PATCH, DELETE) whose Origin is not this site's;
- gives each request an ID, times it, and appends one line to
  data/logs/requests.jsonl with the route, status and time, never a name
  (X9; `python -m chama.pipeline web-stats` summarises it);
- adds security headers.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from chama.web import auth, errors
from chama.web.routes import health, members, officials, records, scans, session
from chama.web.settings import web_settings

log = logging.getLogger("chama.web")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Cache-Control": "no-store",
}


def _write_request_log(line: dict) -> None:
    folder = web_settings().log_dir
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / "requests.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")
    except OSError:
        log.warning("could not write the request log")


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = FastAPI(title="Kibaba API", docs_url=None, redoc_url=None,
                  openapi_url=None)

    app.add_exception_handler(errors.ApiError, errors.api_error_handler)
    app.add_exception_handler(StarletteHTTPException, errors.http_error_handler)
    app.add_exception_handler(RequestValidationError, errors.validation_error_handler)
    app.add_exception_handler(Exception, errors.unexpected_error_handler)

    @app.middleware("http")
    async def timing(request: Request, call_next):
        request_id = errors.new_reference().replace("R-", "Q-")
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        ms = round((time.perf_counter() - start) * 1000, 1)
        route = request.scope.get("route")
        _write_request_log({
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "id": request_id, "method": request.method,
            "route": getattr(route, "path", "unmatched"), "status": response.status_code,
            "ms": ms, "user": getattr(request.state, "user_id", None),
        })
        response.headers["X-Request-ID"] = request_id
        response.headers["Server-Timing"] = f"app;dur={ms}"
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.middleware("http")
    async def same_origin_changes(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin \
                and origin.rstrip("/") not in web_settings().allowed_origins:
            ref = errors.new_reference()
            log.warning("%s %s refused: origin not allowed ref=%s", request.method,
                        request.url.path, ref)
            return JSONResponse({"error": {"code": "origin", "ref": ref,
                                           "message": "Changes can only be made from this site."}},
                                status_code=403)
        return await call_next(request)

    @app.get("/api/openapi.json", include_in_schema=False)
    def api_description(user: auth.Admin) -> dict:
        """The API's description for the future mobile app: admins only (S-6)."""
        return app.openapi()

    app.include_router(health.router)
    app.include_router(session.router)
    app.include_router(officials.router)
    app.include_router(records.router)
    app.include_router(scans.router)
    app.include_router(members.router)
    return app


app = create_app()
