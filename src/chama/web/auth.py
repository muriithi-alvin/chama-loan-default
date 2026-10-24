"""Sign-in, sessions and the role checks every route uses (R1-R4, X1, X2).

Sign-in: the server sends the email and password to Supabase Auth, and only
if Supabase accepts them and the email has an active account in app.users
does it start a session of its own. The browser then holds two cookies:

- chama_session: a random token, HttpOnly, Secure, SameSite=Lax. Only its
  SHA-256 is stored, in app.sessions.
- chama_csrf: the session's CSRF token, readable by the page, which sends it
  back in the X-CSRF-Token header with every change (POST, PUT, PATCH, DELETE).

The role dependencies take the chama and member code from the signed-in
account, never from the address, so changing an ID in a URL cannot reach
another chama's or member's records (R4).
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
from fastapi import Depends, Request, Response
from sqlalchemy.engine import Connection

from chama.web.data import users
from chama.web.data.users import User
from chama.web.db import Conn
from chama.web.errors import ApiError, not_allowed, signed_out
from chama.web.settings import WebSettings, web_settings

SESSION_COOKIE = "chama_session"
CSRF_COOKIE = "chama_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class Identity:
    """Who Supabase says signed in."""

    id: str
    email: str


class SupabaseAuth:
    """Checks an email and password with Supabase Auth (the password grant)."""

    def __init__(self, settings: WebSettings, client: httpx.Client | None = None):
        self.settings = settings
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=15)
        return self._client

    def sign_in(self, email: str, password: str) -> Identity:
        if not self.settings.supabase_ready:
            raise ApiError(503, "sign_in_not_set_up",
                           "Sign-in is not set up on this server yet: SUPABASE_URL and "
                           "SUPABASE_PUBLISHABLE_KEY are missing from .env.")
        try:
            response = self.client.post(
                f"{self.settings.supabase_url}/auth/v1/token",
                params={"grant_type": "password"},
                headers={"apikey": self.settings.supabase_key},
                json={"email": email, "password": password},
            )
        except httpx.RequestError as e:
            raise ApiError(503, "sign_in_unavailable",
                           "The sign-in service is not answering. Try again in a minute.") from e
        if response.status_code in (400, 401, 422):
            raise ApiError(401, "bad_credentials",
                           "That email and password do not match. Check them and try again.",
                           field="password")
        if response.status_code == 429:
            raise ApiError(429, "too_many_attempts",
                           "Too many sign-in attempts. Wait a minute, then try again.")
        if response.status_code != 200:
            raise ApiError(503, "sign_in_unavailable",
                           "The sign-in service is not answering. Try again in a minute.")
        user = response.json().get("user") or {}
        if not user.get("id"):
            raise ApiError(503, "sign_in_unavailable",
                           "The sign-in service gave an unexpected answer. Try again in a minute.")
        return Identity(id=user["id"], email=user.get("email") or email)


def supabase_auth() -> SupabaseAuth:
    """FastAPI dependency; tests replace it with a fake."""
    return SupabaseAuth(web_settings())


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def open_session(conn: Connection, response: Response, user: User, settings: WebSettings) -> str:
    """Start a session for `user` and set its cookies. Returns the CSRF token."""
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.session_hours)
    users.start_session(conn, hash_token(token), user.id, csrf, expires)
    age = settings.session_hours * 3600
    response.set_cookie(SESSION_COOKIE, token, max_age=age, httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/")
    response.set_cookie(CSRF_COOKIE, csrf, max_age=age, httponly=False,
                        secure=settings.cookie_secure, samesite="lax", path="/")
    return csrf


def close_session(conn: Connection, request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        users.end_session(conn, hash_token(token))
    settings = web_settings()
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, samesite="lax")


@dataclass(frozen=True)
class Session:
    user: User
    csrf: str


def current_session(request: Request, conn: Conn) -> Session:
    """The signed-in session; 401 if there is none or it has ended (X1).

    For any change (not GET), the X-CSRF-Token header must match the session's
    token (X2).
    """
    token = request.cookies.get(SESSION_COOKIE)
    found = users.session(conn, hash_token(token)) if token else None
    if not found:
        raise signed_out()
    user, csrf = found
    request.state.user_id = user.id      # logs hold the account number, never a name
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not secrets.compare_digest(sent, csrf):
            raise ApiError(403, "csrf",
                           "This page has been open too long to save changes. Reload it and try again.")
    return Session(user, csrf)


CurrentSession = Annotated[Session, Depends(current_session)]


def signed_in(session: CurrentSession) -> User:
    return session.user


def official(session: CurrentSession) -> User:
    """An official (or the admin) of the signed-in chama (R1)."""
    if not session.user.is_official:
        raise not_allowed()
    return session.user


def member(session: CurrentSession) -> User:
    """A member, who sees their own records only (R2)."""
    if session.user.role != "member" or not session.user.member_code:
        raise not_allowed()
    return session.user


def admin(session: CurrentSession) -> User:
    if session.user.role != "admin":
        raise not_allowed()
    return session.user


# Route parameters typed with these get the signed-in account after the check.
SignedIn = Annotated[User, Depends(signed_in)]
Official = Annotated[User, Depends(official)]
Member = Annotated[User, Depends(member)]
Admin = Annotated[User, Depends(admin)]
Supabase = Annotated[SupabaseAuth, Depends(supabase_auth)]
