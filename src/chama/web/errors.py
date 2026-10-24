"""Errors the API returns: a short code, a message safe to show, and a reference.

Every error response carries a reference such as R-7K3F9Q that also appears
in the server log, so a message on screen can be matched to the log line
(X4). Messages never hold a stack trace, a name or a key.
"""
from __future__ import annotations

import logging
import secrets

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("chama.web")

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I


def new_reference() -> str:
    return "R-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))


class ApiError(Exception):
    """A planned refusal: HTTP status, a code for the page, a message for people.

    `field` names the form field the message is about, so the page can show
    it next to that field (X3).
    """

    def __init__(self, status: int, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.field = field


SIGNED_OUT = "Your session ended. Sign in again to carry on."
NOT_ALLOWED = "This page is not part of your account."


def signed_out() -> ApiError:
    return ApiError(401, "signed_out", SIGNED_OUT)


def not_allowed() -> ApiError:
    return ApiError(403, "not_allowed", NOT_ALLOWED)


def not_found(what: str = "That page") -> ApiError:
    return ApiError(404, "not_found", f"{what} was not found.")


def _body(code: str, message: str, ref: str, field: str | None = None) -> dict:
    error = {"code": code, "message": message, "ref": ref}
    if field:
        error["field"] = field
    return {"error": error}


def _route(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    ref = new_reference()
    request.state.error_ref = ref
    level = logging.WARNING if exc.status in (401, 403) else logging.INFO
    log.log(level, "%s %s -> %s %s ref=%s user=%s", request.method, _route(request), exc.status,
            exc.code, ref, getattr(request.state, "user_id", "-"))
    return JSONResponse(_body(exc.code, exc.message, ref, exc.field), status_code=exc.status)


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    ref = new_reference()
    messages = {404: "That page was not found.", 405: "That action is not available here."}
    message = messages.get(exc.status_code, "The request could not be handled.")
    log.info("%s %s -> %s ref=%s", request.method, request.url.path, exc.status_code, ref)
    return JSONResponse(_body("http_" + str(exc.status_code), message, ref), status_code=exc.status_code)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    ref = new_reference()
    first = exc.errors()[0] if exc.errors() else {}
    location = [str(p) for p in first.get("loc", []) if p not in ("body", "query", "path")]
    field = location[0] if location else None
    log.info("%s %s -> 422 invalid field=%s ref=%s", request.method, _route(request), field, ref)
    return JSONResponse(
        _body("invalid", "Some of the details sent were not in the expected form.", ref, field),
        status_code=422,
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    ref = new_reference()
    log.exception("%s %s -> 500 ref=%s", request.method, _route(request), ref)
    return JSONResponse(
        _body("server_error",
              f"The server could not finish this request. Try again; if it happens again, "
              f"give the reference {ref} to the admin.", ref),
        status_code=500,
    )
