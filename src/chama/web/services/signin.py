"""The ways to sign in, and the texted code officials confirm with (D-037).

    email + password ─┐
    Google ───────────┴─> member: session   official: code to their phone ─> session
    phone + code ─────────> member: session   (officials use one of the two above)

Supabase Auth checks the password, Google and the texted codes; this module
decides which account the person may open and whether a code is still needed.
An official's second step is a code texted to the phone on their account, so a
stolen password or Google sign-in alone opens nothing. Codes are only ever sent
to numbers that have an active account, so nobody can make the chama pay for
texts to other numbers.

A sign-in waiting for its code lasts 10 minutes and allows 5 tries (app.signin_steps).
"""
from __future__ import annotations

from fastapi import Request, Response
from sqlalchemy.engine import Connection

from chama.web import auth
from chama.web.data import users
from chama.web.data.users import User
from chama.web.errors import ApiError
from chama.web.settings import WebSettings

NO_ACCESS = "This account has no access to a chama yet. Ask your chama's admin to add it."
MISMATCH = "This sign-in does not match the account on record. Ask your chama's admin to check it."


def needs_code(user: User, settings: WebSettings) -> bool:
    return user.is_official and settings.two_step_for_officials


def check_account(user: User | None, identity: auth.Identity, kind: str) -> User:
    """The active account this identity may open (an email or a phone sign-in)."""
    if user is None or not user.active:
        raise ApiError(403, "no_access", NO_ACCESS)
    linked = user.identity_id if kind == "email" else user.phone_identity_id
    if linked and linked != identity.id:
        raise ApiError(403, "mismatch", MISMATCH)
    return user


def first_step_done(conn: Connection, response: Response, user: User | None, identity: auth.Identity,
                    method: str, supabase: auth.SupabaseAuth, settings: WebSettings) -> dict | None:
    """After a password or Google: None once a session is open, or what the code
    page needs when an official must still type a texted code."""
    user = check_account(user, identity, "email")
    if not needs_code(user, settings):
        users.link_identity(conn, user.id, identity.id)
        auth.open_session(conn, response, user, settings)
        return None
    if not user.phone:
        raise ApiError(403, "no_phone", "Officials confirm each sign-in with a code texted to their phone, and "
                       "this account has no phone number yet. Ask your chama's admin to add it.")
    supabase.send_code(user.phone)
    auth.start_step(conn, response, user, method, identity.id, settings)
    return {"next": "code", "phone_hint": auth.phone_hint(user.phone)}


def start_phone(conn: Connection, response: Response, written: str, supabase: auth.SupabaseAuth,
                settings: WebSettings) -> dict:
    phone = auth.normalise_phone(written, settings.phone_country)
    if phone is None:
        raise ApiError(422, "phone_invalid", "Enter the phone number as 07XX XXX XXX or +254 7XX XXX XXX.",
                       field="phone")
    user = users.by_phone(conn, phone)
    if user is None or not user.active:
        raise ApiError(403, "no_access", "This phone number has no account in a chama. Ask your chama's "
                       "admin to add it.", field="phone")
    if needs_code(user, settings):
        raise ApiError(403, "official_phone", "Officials sign in with Google or their email and password first. "
                       "A code is then texted to this phone.", field="phone")
    supabase.send_code(phone)
    auth.start_step(conn, response, user, "phone", None, settings)
    return {"next": "code", "phone_hint": auth.phone_hint(phone)}


def _waiting(conn: Connection, request: Request) -> tuple[dict, User]:
    step = auth.waiting_step(conn, request)
    user = users.by_id(conn, step["user_id"]) if step else None
    if step is None or user is None or not user.active:
        raise ApiError(401, "step_ended", "This sign-in has ended. Start again.")
    return step, user


def waiting(conn: Connection, request: Request) -> dict:
    """For the code page: whether a sign-in is waiting, and where the code went."""
    try:
        step, user = _waiting(conn, request)
    except ApiError:
        return {"waiting": False}
    return {"waiting": True, "method": step["method"], "phone_hint": auth.phone_hint(user.phone)}


def resend(conn: Connection, request: Request, supabase: auth.SupabaseAuth) -> dict:
    _, user = _waiting(conn, request)
    supabase.send_code(user.phone)
    return {"sent": True, "phone_hint": auth.phone_hint(user.phone)}


def enter_code(conn: Connection, request: Request, response: Response, code: str,
               supabase: auth.SupabaseAuth, settings: WebSettings) -> User | ApiError:
    """The account once its code is right. A wrong code is counted and returned
    (not raised), so the count is saved; the fifth wrong code ends the sign-in."""
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) != 6:
        return ApiError(422, "code_missing", "Enter the 6-digit code from the text message.", field="code")
    step, user = _waiting(conn, request)
    try:
        identity = supabase.verify_code(user.phone, code)
    except ApiError as e:
        if e.code != "bad_code":
            raise
        left = auth.MAX_CODE_TRIES - users.count_attempt(conn, step["token_hash"])
        if left <= 0:
            users.end_step(conn, step["token_hash"])
            auth.clear_step(response, settings)
            return ApiError(401, "step_ended", "Too many wrong codes. Start signing in again.")
        return ApiError(401, "bad_code", f"{e.message} ({left} {'try' if left == 1 else 'tries'} left)",
                        field="code")
    check_account(user, identity, "phone")
    users.link_phone_identity(conn, user.id, identity.id)
    if step["identity_id"]:
        users.link_identity(conn, user.id, step["identity_id"])
    users.end_step(conn, step["token_hash"])
    auth.clear_step(response, settings)
    auth.open_session(conn, response, user, settings)
    return user
