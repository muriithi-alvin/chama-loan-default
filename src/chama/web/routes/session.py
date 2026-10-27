"""Signing in and out, and who is signed in (X1, X2)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection

from chama.web import auth
from chama.web.data import users
from chama.web.data.users import User
from chama.web.db import Conn
from chama.web.errors import ApiError
from chama.web.services.names import display_name, member_names
from chama.web.settings import chama_name, is_demo_chama, web_settings

router = APIRouter(prefix="/api")
log = logging.getLogger("chama.web")


class SignIn(BaseModel):
    email: str = ""
    password: str = ""


def me(conn: Connection, user: User) -> dict:
    """What every page shows about the signed-in person (section 6)."""
    settings = web_settings()
    if user.role == "member":
        name = display_name(member_names(conn, user.chama_id), user.member_code)
    elif settings.demo_mode and not is_demo_chama(user.chama_id):
        name = (user.position or "Official").capitalize()   # a real official's name stays off screen
    else:
        name = user.display_name or user.email.split("@")[0]
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
def site() -> dict:
    """What the sign-in page needs before anyone signs in."""
    settings = web_settings()
    return {"demo_mode": settings.demo_mode, "sign_in_ready": settings.supabase_ready}


@router.post("/session")
def sign_in(body: SignIn, response: Response, conn: Conn, supabase: auth.Supabase) -> dict:
    email = body.email.strip()
    if not email or "@" not in email:
        raise ApiError(422, "email_missing", "Enter the email address of your account.", field="email")
    if not body.password:
        raise ApiError(422, "password_missing", "Enter your password.", field="password")

    identity = supabase.sign_in(email, body.password)
    user = users.by_email(conn, identity.email)
    if user is None or not user.active:
        raise ApiError(403, "no_access", "This account has no access to a chama yet. "
                       "Ask your chama's admin to add it.")
    if user.identity_id and user.identity_id != identity.id:
        raise ApiError(403, "no_access", "This sign-in does not match the account on record. "
                       "Ask your chama's admin to check it.")
    users.link_identity(conn, user.id, identity.id)
    auth.open_session(conn, response, user, web_settings())
    log.info("sign-in user=%s role=%s chama=%s", user.id, user.role, user.chama_id)
    return me(conn, user)


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
