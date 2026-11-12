"""Signing in and out, and who is signed in (X1, X2, D-037).

    POST /api/session                  email and password
    GET  /api/session/google           to Google, through Supabase (PKCE)
    GET  /api/session/google/callback  back from Google
    POST /api/session/phone            a member's phone number: a code is texted
    GET  /api/session/step             is a sign-in waiting for its code?
    POST /api/session/code             the texted code; then the session starts
    POST /api/session/code/resend
    DELETE /api/session                sign out
"""
from __future__ import annotations

import logging
import re
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection

from chama.web import auth
from chama.web.data import users
from chama.web.data.users import User
from chama.web.db import Conn
from chama.web.errors import ApiError, as_response
from chama.web.services import signin
from chama.web.services.names import display_name, member_names
from chama.web.settings import WebSettings, chama_name, is_demo_chama, web_settings

router = APIRouter(prefix="/api")
log = logging.getLogger("chama.web")

PAGE = re.compile(r"/(o|m)(/[A-Za-z0-9/_-]*)?")


class SignIn(BaseModel):
    email: str = ""
    password: str = ""


class Phone(BaseModel):
    phone: str = ""


class Code(BaseModel):
    code: str = ""


def _landing(user: User, next_page: str | None = None) -> str:
    """Where a signed-in person goes: the page they asked for, if it is theirs."""
    theirs = next_page and ((next_page.startswith("/m") and user.role == "member")
                            or (next_page.startswith("/o") and user.is_official))
    if theirs and PAGE.fullmatch(next_page):
        return next_page
    return "/m" if user.role == "member" else "/o"


def _public_origin(request: Request, settings: WebSettings) -> str:
    """The address the browser is on, if it is one of this site's; else the first."""
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",")[0].strip()
    origin = f"{proto}://{host}".rstrip("/")
    return origin if origin in settings.allowed_origins else settings.allowed_origins[0]


def _with_cookies(reply: JSONResponse, response: Response) -> JSONResponse:
    """A returned response leaves out the cookies set on `response`; add them."""
    for name, value in response.headers.raw:
        if name == b"set-cookie":
            reply.headers.raw.append((name, value))
    return reply


def me(conn: Connection, user: User) -> dict:
    """What every page shows about the signed-in person (section 6)."""
    settings = web_settings()
    if user.role == "member":
        name = display_name(member_names(conn, user.chama_id), user.member_code)
    elif settings.demo_mode and not is_demo_chama(user.chama_id):
        name = (user.position or "Official").capitalize()   # a real official's name stays off screen
    else:
        name = user.display_name or (user.email or user.phone or "Official").split("@")[0]
    return {
        "user": {
            "name": name,
            "role": user.role,
            "position": user.position,
            "chama_id": user.chama_id,
            "chama_name": chama_name(user.chama_id),
            "member_code": user.member_code,
        },
        "demo_mode": settings.demo_mode or is_demo_chama(user.chama_id),
    }


@router.get("/site")
def site(supabase: auth.Supabase) -> dict:
    """What the sign-in page needs before anyone signs in."""
    settings = web_settings()
    providers = supabase.providers()
    return {"demo_mode": settings.demo_mode, "sign_in_ready": settings.supabase_ready,
            "methods": {"password": settings.supabase_ready and providers.get("email", True),
                        "google": providers.get("google", False), "phone": providers.get("phone", False)},
            "officials_confirm_by_phone": settings.two_step_for_officials}


@router.post("/session")
def sign_in(body: SignIn, response: Response, conn: Conn, supabase: auth.Supabase) -> dict:
    email = body.email.strip()
    if not email or "@" not in email:
        raise ApiError(422, "email_missing", "Enter the email address of your account.", field="email")
    if not body.password:
        raise ApiError(422, "password_missing", "Enter your password.", field="password")

    identity = supabase.sign_in(email, body.password)
    user = users.by_email(conn, identity.email)
    waiting = signin.first_step_done(conn, response, user, identity, "password", supabase, web_settings())
    if waiting:
        log.info("sign-in user=%s: password right, code sent", user.id)
        return waiting
    log.info("sign-in user=%s role=%s chama=%s method=password", user.id, user.role, user.chama_id)
    return me(conn, user)


@router.get("/session/google")
def google(request: Request, supabase: auth.Supabase, next: Annotated[str, Query()] = "") -> RedirectResponse:
    """Off to Google through Supabase; the PKCE verifier stays in this browser."""
    settings = web_settings()
    if not supabase.providers().get("google"):
        return RedirectResponse("/signin?error=google_off", status_code=303)
    verifier, challenge = auth.pkce_pair()
    back = f"{_public_origin(request, settings)}/api/session/google/callback"
    reply = RedirectResponse(supabase.google_url(back, challenge), status_code=303)
    keep = next if PAGE.fullmatch(next or "") else ""
    reply.set_cookie(auth.PKCE_COOKIE, f"{verifier}|{keep}", max_age=600, httponly=True,
                     secure=settings.cookie_secure, samesite="lax", path="/api/session/google")
    return reply


@router.get("/session/google/callback")
def google_back(request: Request, conn: Conn, supabase: auth.Supabase, code: str = "",
                error: str = "") -> RedirectResponse:
    """Back from Google: the code and this browser's verifier give the person's email."""
    settings = web_settings()
    verifier, _, next_page = (request.cookies.get(auth.PKCE_COOKIE) or "").partition("|")
    reply = RedirectResponse("/signin?error=google_failed", status_code=303)
    reply.delete_cookie(auth.PKCE_COOKIE, path="/api/session/google", secure=settings.cookie_secure,
                        samesite="lax")
    if error or not code or not verifier:
        log.info("google sign-in did not finish (error=%s, code=%s, verifier=%s)", error or "-", bool(code),
                 bool(verifier))
        return reply
    try:
        identity = supabase.exchange_code(code, verifier)
        user = users.by_email(conn, identity.email)
        waiting = signin.first_step_done(conn, reply, user, identity, "google", supabase, settings)
    except ApiError as e:
        log.info("google sign-in refused: %s", e.code)
        reply.headers["location"] = f"/signin?error={e.code}"
        return reply
    if waiting:
        log.info("sign-in user=%s: google done, code sent", user.id)
        reply.headers["location"] = "/signin?step=code" + (f"&next={next_page}" if next_page else "")
    else:
        log.info("sign-in user=%s role=%s chama=%s method=google", user.id, user.role, user.chama_id)
        reply.headers["location"] = _landing(user, next_page)
    return reply


@router.post("/session/phone")
def phone_sign_in(body: Phone, response: Response, conn: Conn, supabase: auth.Supabase) -> dict:
    """A member's phone number: Supabase texts a code to it."""
    return signin.start_phone(conn, response, body.phone, supabase, web_settings())


@router.get("/session/step")
def step(request: Request, conn: Conn) -> dict:
    return signin.waiting(conn, request)


@router.post("/session/code")
def code(body: Code, request: Request, response: Response, conn: Conn, supabase: auth.Supabase):
    result = signin.enter_code(conn, request, response, body.code, supabase, web_settings())
    if isinstance(result, ApiError):
        return _with_cookies(as_response(request, result), response)
    log.info("sign-in user=%s role=%s chama=%s: code right", result.id, result.role, result.chama_id)
    return me(conn, result)


@router.post("/session/code/resend")
def resend(request: Request, conn: Conn, supabase: auth.Supabase) -> dict:
    return signin.resend(conn, request, supabase)


@router.delete("/session")
def sign_out(request: Request, response: Response, conn: Conn) -> dict:
    """Ends the session. Works even when it has already ended."""
    auth.close_session(conn, request, response)
    return {"signed_out": True}


@router.get("/me")
def who(conn: Conn, user: auth.SignedIn) -> dict:
    return me(conn, user)


@router.get("/records-status")
def records_status(conn: Conn, user: auth.SignedIn) -> dict:
    """For the footer of every page: how far the records go and, for officials,
    which model run made the scores. Members get no score details (R2)."""
    from chama.db import table_exists
    from chama.web.data import records
    from chama.web.services.early_warning import model_label

    last = records.latest_meeting(conn, user.chama_id) if table_exists(conn, "analytics.meetings") else None
    status = {"records_to": {k: last[k] for k in ("page_no", "meeting_month", "meeting_date")} if last else None}
    if user.is_official:
        scored = conn.execute(text(
            "SELECT model_name, model_run_id, scored_at FROM app.risk_scores WHERE chama_id = :c "
            "ORDER BY scored_at DESC LIMIT 1"), {"c": user.chama_id}).first()
        status["model_label"] = model_label(scored.model_name, scored.model_run_id) if scored else None
        status["scored_at"] = scored.scored_at if scored else None
    return status
