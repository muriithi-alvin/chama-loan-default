"""Sign-in, sessions and the role checks every route uses (R1-R4, X1, X2).

Sign-in (D-037) is Supabase Auth's, in three ways, each done by this server:

- email and password: sent to Supabase (the password grant);
- Google: Supabase's sign-in with Google, with PKCE: the code verifier is
  kept in an HttpOnly cookie, and the code Supabase sends back is exchanged
  for the person's verified email here, never in the page;
- a phone number: Supabase texts a 6-digit code and checks it.

Only if Supabase accepts them and the email or phone has an active account in
app.users does a session of the app's own start. An official must also type a
code texted to the account's phone (routes/session.py). The browser then holds
two cookies:

- chama_session: a random token, HttpOnly, Secure, SameSite=Lax. Only its
  SHA-256 is stored, in app.sessions.
- chama_csrf: the session's CSRF token, readable by the page, which sends it
  back in the X-CSRF-Token header with every change (POST, PUT, PATCH, DELETE).

The role dependencies take the chama and member code from the signed-in
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
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class Identity:
    """Who Supabase says signed in."""

    id: str
    email: str
    phone: str = ""


UNAVAILABLE = "The sign-in service is not answering. Try again in a minute."
NOT_SET_UP = ("Sign-in is not set up on this server yet: SUPABASE_URL and "
              "SUPABASE_PUBLISHABLE_KEY are missing from .env.")
_PROVIDERS: dict[str, tuple[float, dict[str, bool]]] = {}   # Supabase's switched-on providers, for 5 minutes


def normalise_phone(written: str, country: str = "254") -> str | None:
    """A phone number in the +<country><number> form Supabase texts to, or None.

    07.. and 01.. (and 7.., 1..) are read as numbers in `country` (Kenya)."""
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


def phone_hint(phone: str | None) -> str:
    """The last three digits only, as the code page shows them."""
    return f"the phone ending {phone[-3:]}" if phone and len(phone) > 3 else "your phone"


def pkce_pair() -> tuple[str, str]:
    """(code verifier, its S256 challenge), RFC 7636."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=")
    return verifier, challenge.decode("ascii")


class SupabaseAuth:
    """Supabase Auth's REST API: passwords, Google with PKCE, and texted codes."""

    def __init__(self, settings: WebSettings, client: httpx.Client | None = None):
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
            return self.client.request(method, f"{self.settings.supabase_url}/auth/v1/{path}",
                                       headers={"apikey": self.settings.supabase_key}, **kwargs)
        except httpx.RequestError as e:
            raise ApiError(503, "sign_in_unavailable", UNAVAILABLE) from e

    @staticmethod
    def _identity(response: httpx.Response, email: str = "") -> Identity:
        if response.status_code == 429:
            raise ApiError(429, "too_many_attempts", "Too many sign-in attempts. Wait a minute, then try again.")
        if response.status_code != 200:
            raise ApiError(503, "sign_in_unavailable", UNAVAILABLE)
        user = response.json().get("user") or {}
        if not user.get("id"):
            raise ApiError(503, "sign_in_unavailable",
                           "The sign-in service gave an unexpected answer. Try again in a minute.")
        phone = user.get("phone") or ""
        return Identity(id=user["id"], email=user.get("email") or email,
                        phone=("+" + phone.lstrip("+")) if phone else "")

    def sign_in(self, email: str, password: str) -> Identity:
        response = self._call("POST", "token", params={"grant_type": "password"},
                              json={"email": email, "password": password})
        if response.status_code in (400, 401, 422):
            raise ApiError(401, "bad_credentials",
                           "That email and password do not match. Check them and try again.",
                           field="password")
        return self._identity(response, email)

    def providers(self) -> dict[str, bool]:
        """Which of Google and phone codes are switched on in Supabase (cached 5 minutes)."""
        if not self.settings.supabase_ready:
            return {"google": False, "phone": False}
        cached = _PROVIDERS.get(self.settings.supabase_url)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            response = self._call("GET", "settings")
            external = response.json().get("external", {}) if response.status_code == 200 else {}
        except (ApiError, ValueError):
            external = {}
        found = {"google": bool(external.get("google")), "phone": bool(external.get("phone"))}
        _PROVIDERS[self.settings.supabase_url] = (time.monotonic() + (300 if external else 30), found)
        return found

    def google_url(self, redirect_to: str, challenge: str) -> str:
        """Where the browser goes to sign in with Google; Supabase sends it back to
        `redirect_to` with ?code=..., which must be in its list of redirect URLs."""
        if not self.settings.supabase_ready:
            raise ApiError(503, "sign_in_not_set_up", NOT_SET_UP)
        query = urlencode({"provider": "google", "redirect_to": redirect_to, "code_challenge": challenge,
                           "code_challenge_method": "s256"})
        return f"{self.settings.supabase_url}/auth/v1/authorize?{query}"

    def exchange_code(self, code: str, verifier: str) -> Identity:
        """The code from Google's round trip, with this browser's verifier, for the person."""
        response = self._call("POST", "token", params={"grant_type": "pkce"},
                              json={"auth_code": code, "code_verifier": verifier})
        if response.status_code in (400, 401, 403, 404, 422):
            raise ApiError(401, "google_failed", "Signing in with Google did not finish. Try again.")
        identity = self._identity(response)
        if not identity.email:
            raise ApiError(401, "google_failed", "Google did not give an email address for this account.")
        return identity

    def send_code(self, phone: str) -> None:
        """Supabase texts a 6-digit code to `phone`. Only numbers with an account get here,
        so Supabase may make its phone user on the first code."""
        response = self._call("POST", "otp", json={"phone": phone, "create_user": True})
        if response.status_code == 200:
            return
        message = ""
        try:
            body = response.json()
            message = str(body.get("msg") or body.get("message") or body.get("error_description") or "").lower()
        except ValueError:
            pass
        if response.status_code == 429 or "security purposes" in message or "rate limit" in message:
            raise ApiError(429, "too_many_codes",
                           "A code was sent a moment ago. Wait a minute before asking for another.")
        if "invalid" in message and "phone" in message:
            raise ApiError(422, "phone_invalid", "That phone number could not be used. Check it and try again.",
                           field="phone")
        if "signup" in message.replace(" ", "").replace("-", ""):
            raise ApiError(503, "phone_not_set_up",
                           "This phone has not had a code before, and Supabase does not allow new sign-ins. The admin "
                           "needs to allow sign-ups in Supabase (see docs/web_setup.md).")
        if response.status_code in (400, 422):
            raise ApiError(503, "phone_not_set_up",
                           "Codes by text message are not set up yet. The admin needs to turn on phone "
                           "sign-in in Supabase (see docs/web_setup.md).")
        raise ApiError(503, "sign_in_unavailable", UNAVAILABLE)

    def verify_code(self, phone: str, code: str) -> Identity:
        response = self._call("POST", "verify", json={"type": "sms", "phone": phone, "token": code})
        if response.status_code in (400, 401, 403, 404, 422):
            raise ApiError(401, "bad_code", "That code is not right, or it has expired. Check the text message "
                           "and try again.", field="code")
        return self._identity(response)


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
    clear_step(response, settings)


# ---- A sign-in waiting for its texted code (D-037) ----------------------------------

SIGNIN_COOKIE = "chama_signin"     # HttpOnly, sent only to /api/session/...
PKCE_COOKIE = "chama_pkce"         # the Google round trip's code verifier
STEP_MINUTES = 10
MAX_CODE_TRIES = 5


def start_step(conn: Connection, response: Response, user: User, method: str, identity_id: str | None,
               settings: WebSettings) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=STEP_MINUTES)
    users.start_step(conn, hash_token(token), user.id, method, identity_id, expires)
    response.set_cookie(SIGNIN_COOKIE, token, max_age=STEP_MINUTES * 60, httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/api/session")


def waiting_step(conn: Connection, request: Request) -> dict | None:
    token = request.cookies.get(SIGNIN_COOKIE)
    return users.step(conn, hash_token(token)) if token else None


def clear_step(response: Response, settings: WebSettings) -> None:
    response.delete_cookie(SIGNIN_COOKIE, path="/api/session", secure=settings.cookie_secure, samesite="lax")


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
