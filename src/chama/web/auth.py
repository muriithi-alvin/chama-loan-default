
"""Google sign-in, secure sessions and role checks (R1-R4, X1, X2).

Google authentication is handled by Supabase Auth using PKCE. The code
verifier stays in an HttpOnly cookie and is exchanged by this server.

A Kibaba session is created only after the Google identity is matched to
an active account in app.users. Application roles and permissions always
come from the Kibaba database, never from Google.

The browser holds two cookies:

- chama_session: a random token, HttpOnly, Secure, SameSite=Lax. Only its
  SHA-256 hash is stored in app.sessions.
- chama_csrf: the session's CSRF token, readable by the page, which sends
  it back in the X-CSRF-Token header with every change (POST, PUT, PATCH,
  DELETE).

Phone numbers remain part of account records and may be used by separate
meeting-reminder services. They are not used for authentication.

Role dependencies take the chama and member code from the signed-in
account, never from the address, so changing an ID in a URL cannot reach
another chama's or member's records (R4).
"""
from __future__ import annotations

import base64
import hashlib
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode

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
PKCE_COOKIE = "chama_pkce"

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

UNAVAILABLE = "The sign-in service is not answering. Try again in a minute."
NOT_SET_UP = (
    "Sign-in is not set up on this server yet: SUPABASE_URL and "
    "SUPABASE_PUBLISHABLE_KEY are missing from .env."
)

# Supabase's enabled providers, cached for five minutes.
_PROVIDERS: dict[str, tuple[float, dict[str, bool]]] = {}


@dataclass(frozen=True)
class Identity:
    """The Google identity returned by Supabase."""

    id: str
    email: str
    phone: str = ""


def normalise_phone(written: str, country: str = "254") -> str | None:
    """Convert a phone number to +<country><number>, or return None.

    07.. and 01.. (and 7.., 1..) are interpreted as numbers in `country`.
    This is retained for account records and reminder functionality.
    """
    digits = re.sub(r"[\s().-]", "", written or "")

    if digits.startswith("00"):
        digits = "+" + digits[2:]

    if digits.startswith("+"):
        return digits if re.fullmatch(r"\+[1-9]\d{7,14}", digits) else None

    if not digits.isdigit():
        return None

    if digits.startswith(country) and len(digits) == len(country) + 9:
        return "+" + digits

    if len(digits) == 10 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) == 9 and digits[0] in "17":
        return f"+{country}{digits}"

    return None


def pkce_pair() -> tuple[str, str]:
    """Return a PKCE code verifier and its S256 challenge (RFC 7636)."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=")

    return verifier, challenge.decode("ascii")


class SupabaseAuth:
    """Supabase Auth REST client for Google sign-in with PKCE."""

    def __init__(
        self,
        settings: WebSettings,
        client: httpx.Client | None = None,
    ):
        self.settings = settings
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=15)
        return self._client

    def _call(self, method: str, path: str, **kwargs) -> httpx.Response:
        if not self.settings.supabase_ready:
            raise ApiError(503, "sign_in_not_set_up", NOT_SET_UP)

        try:
            return self.client.request(
                method,
                f"{self.settings.supabase_url}/auth/v1/{path}",
                headers={"apikey": self.settings.supabase_key},
                **kwargs,
            )
        except httpx.RequestError as exc:
            raise ApiError(
                503,
                "sign_in_unavailable",
                UNAVAILABLE,
            ) from exc

    @staticmethod
    def _identity(response: httpx.Response) -> Identity:
        """Extract the authenticated identity from Supabase's response."""
        if response.status_code == 429:
            raise ApiError(
                429,
                "too_many_attempts",
                "Too many sign-in attempts. Wait a minute, then try again.",
            )

        if response.status_code != 200:
            raise ApiError(503, "sign_in_unavailable", UNAVAILABLE)

        user = response.json().get("user") or {}

        if not user.get("id"):
            raise ApiError(
                503,
                "sign_in_unavailable",
                "The sign-in service gave an unexpected answer. "
                "Try again in a minute.",
            )

        email = user.get("email") or ""

        phone = user.get("phone") or ""
        if phone:
            phone = "+" + phone.lstrip("+")

        return Identity(
            id=user["id"],
            email=email,
            phone=phone,
        )

    def providers(self) -> dict[str, bool]:
        """Return whether Google sign-in is enabled in Supabase.

        The result is cached for five minutes.
        """
        if not self.settings.supabase_ready:
            return {"google": False}

        cached = _PROVIDERS.get(self.settings.supabase_url)

        if cached and cached[0] > time.monotonic():
            return cached[1]

        try:
            response = self._call("GET", "settings")
            external = (
                response.json().get("external", {})
                if response.status_code == 200
                else {}
            )
        except (ApiError, ValueError):
            external = {}

        found = {
            "google": bool(external.get("google")),
        }

        _PROVIDERS[self.settings.supabase_url] = (
            time.monotonic() + (300 if external else 30),
            found,
        )

        return found

    def google_url(self, redirect_to: str, challenge: str) -> str:
        """Build the Supabase Google OAuth authorization URL."""
        if not self.settings.supabase_ready:
            raise ApiError(503, "sign_in_not_set_up", NOT_SET_UP)

        query = urlencode(
            {
                "provider": "google",
                "redirect_to": redirect_to,
                "code_challenge": challenge,
                "code_challenge_method": "s256",
            }
        )

        return f"{self.settings.supabase_url}/auth/v1/authorize?{query}"

    def exchange_code(self, code: str, verifier: str) -> Identity:
        """Exchange Google's OAuth callback code using the PKCE verifier."""
        response = self._call(
            "POST",
            "token",
            params={"grant_type": "pkce"},
            json={
                "auth_code": code,
                "code_verifier": verifier,
            },
        )

        if response.status_code in (400, 401, 403, 404, 422):
            raise ApiError(
                401,
                "google_failed",
                "Signing in with Google did not finish. Try again.",
            )

        identity = self._identity(response)

        if not identity.email:
            raise ApiError(
                401,
                "google_failed",
                "Google did not give an email address for this account.",
            )

        return identity


def supabase_auth() -> SupabaseAuth:
    """FastAPI dependency; tests can replace this with a fake."""
    return SupabaseAuth(web_settings())


def hash_token(token: str) -> str:
    """Hash a session token before storing or looking it up."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def open_session(
    conn: Connection,
    response: Response,
    user: User,
    settings: WebSettings,
) -> str:
    """Start a Kibaba session and set its cookies.

    Returns the CSRF token.
    """
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)

    expires = datetime.now(timezone.utc) + timedelta(
        hours=settings.session_hours
    )

    users.start_session(
        conn,
        hash_token(token),
        user.id,
        csrf,
        expires,
    )

    age = settings.session_hours * 3600

    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )

    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )

    return csrf


def close_session(
    conn: Connection,
    request: Request,
    response: Response,
) -> None:
    """End the current session and remove its browser cookies."""
    token = request.cookies.get(SESSION_COOKIE)

    if token:
        users.end_session(conn, hash_token(token))

    settings = web_settings()

    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(
            name,
            path="/",
            secure=settings.cookie_secure,
            samesite="lax",
        )


@dataclass(frozen=True)
class Session:
    user: User
    csrf: str


def current_session(request: Request, conn: Conn) -> Session:
    """Return the signed-in session or raise 401 if it has ended.

    For every change request, the X-CSRF-Token header must match the
    token stored with the session.
    """
    token = request.cookies.get(SESSION_COOKIE)

    found = users.session(conn, hash_token(token)) if token else None

    if not found:
        raise signed_out()

    user, csrf = found

    # Logs hold the account ID, never the member's name.
    request.state.user_id = user.id

    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")

        if not secrets.compare_digest(sent, csrf):
            raise ApiError(
                403,
                "csrf",
                "This page has been open too long to save changes. "
                "Reload it and try again.",
            )

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
    """Require an administrator account."""
    if session.user.role != "admin":
        raise not_allowed()

    return session.user


# Route parameters typed with these dependencies receive the signed-in
# account only after the corresponding authorization check.
SignedIn = Annotated[User, Depends(signed_in)]
Official = Annotated[User, Depends(official)]
Member = Annotated[User, Depends(member)]
Admin = Annotated[User, Depends(admin)]
Supabase = Annotated[SupabaseAuth, Depends(supabase_auth)]
