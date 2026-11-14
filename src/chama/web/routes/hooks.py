"""Calls from Supabase, not from people (D-042).

    POST /api/hooks/send-sms   Supabase's Send SMS hook: text a sign-in code
                               through Africa's Talking (services/sms_hook.py)

No session or CSRF token: the hook proves itself with its signature. The
answer is the shape Supabase expects: {} when sent, otherwise
{"error": {"http_code": ..., "message": ...}}, both as JSON.
"""
from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from chama.web.data import users
from chama.web.db import Conn
from chama.web.services import sms_hook

router = APIRouter(prefix="/api/hooks")
log = logging.getLogger("chama.web")


def sms_settings() -> sms_hook.SmsSettings:
    """From .env (or the Space's secrets); tests replace it."""
    return sms_hook.SmsSettings.from_env()


def sms_client() -> httpx.Client | None:
    """None: a real client with a 4-second limit; tests give a fake one."""
    return None


@router.post("/send-sms")
async def send_sms(request: Request, conn: Conn,
                   settings: Annotated[sms_hook.SmsSettings, Depends(sms_settings)],
                   client: Annotated[httpx.Client | None, Depends(sms_client)]) -> JSONResponse:
    body = await request.body()

    def has_account(phone: str) -> bool:
        user = users.by_phone(conn, phone)
        return bool(user and user.active)

    try:
        await run_in_threadpool(sms_hook.handle, settings, request.headers, body, has_account, client)
    except sms_hook.HookRefused as e:
        log.info("sms hook refused: %s %s", e.status, e.message)
        return JSONResponse({"error": {"http_code": e.status, "message": e.message}}, status_code=e.status)
    return JSONResponse({}, status_code=200)
