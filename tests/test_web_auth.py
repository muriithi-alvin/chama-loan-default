"""Sign-in, sessions, CSRF and role checks (X1, X2, R1-R4, D-037), without a database.

The account and session queries are replaced by an in-memory store and
Supabase by a fake, so every rule of auth.py and services/signin.py is
checked on its own: passwords, Google with PKCE, texted codes, and the code
officials confirm every sign-in with.
"""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from typing import ClassVar
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from chama.web import auth
from chama.web.data import users as users_data
from chama.web.data.users import User
from chama.web.db import connection
from chama.web.errors import ApiError
from chama.web.routes import officials, session
from chama.web.settings import web_settings

OFFICIAL = User(1, "alvin@example.com", "official", "chama_demo", None, "Alvin Muriithi", "treasurer", True,
                phone="+254700000001")
MEMBER = User(2, "wise@example.com", "member", "chama_demo", "M-aaaa1111", None, None, True, phone="+254700000002")
OTHER_CHAMA = User(3, "other@example.com", "official", "chama_b", None, "Someone", "chair", True,
                   phone="+254700000003")
GONE = User(4, "gone@example.com", "official", "chama_demo", None, "Gone", None, False, phone="+254700000004")
NO_PHONE = User(5, "nophone@example.com", "official", "chama_demo", None, "No Phone", "secretary", True)
RIGHT_CODE = "123456"


class FakeStore:
    def __init__(self):
        self.accounts = {u.email: u for u in (OFFICIAL, MEMBER, OTHER_CHAMA, GONE, NO_PHONE)}
        self.sessions: dict[str, tuple[int, str, bool]] = {}
        self.steps: dict[str, dict] = {}
        self.linked: dict[int, dict[str, str]] = {}

    def by_email(self, conn, email):
        return self.accounts.get(email.strip().lower())

    def by_phone(self, conn, phone):
        return next((u for u in self.accounts.values() if u.phone == phone), None)

    def by_id(self, conn, user_id):
        return next((u for u in self.accounts.values() if u.id == user_id), None)

    def link_identity(self, conn, user_id, identity_id):
        self.linked.setdefault(user_id, {}).setdefault("email", identity_id)

    def link_phone_identity(self, conn, user_id, identity_id):
        self.linked.setdefault(user_id, {}).setdefault("phone", identity_id)

    def start_session(self, conn, token_hash, user_id, csrf, expires_at):
        assert expires_at > datetime.now(timezone.utc)
        self.sessions[token_hash] = (user_id, csrf, True)

    def session(self, conn, token_hash):
        found = self.sessions.get(token_hash)
        if not found or not found[2]:
            return None
        user = next(u for u in self.accounts.values() if u.id == found[0])
        return (user, found[1]) if user.active else None

    def end_session(self, conn, token_hash):
        if token_hash in self.sessions:
            user_id, csrf, _ = self.sessions[token_hash]
            self.sessions[token_hash] = (user_id, csrf, False)

    def start_step(self, conn, token_hash, user_id, method, identity_id, expires_at):
        self.steps[token_hash] = {"token_hash": token_hash, "user_id": user_id, "method": method,
                                  "identity_id": identity_id, "attempts": 0, "used": False}

    def step(self, conn, token_hash):
        found = self.steps.get(token_hash)
        return dict(found) if found and not found["used"] else None

    def count_attempt(self, conn, token_hash):
        self.steps[token_hash]["attempts"] += 1
        return self.steps[token_hash]["attempts"]

    def end_step(self, conn, token_hash):
        self.steps[token_hash]["used"] = True


class FakeSupabase:
    passwords: ClassVar[dict[str, str]] = {}
    texts: ClassVar[list[str]] = []                       # phones a code was sent to
    google_codes: ClassVar[dict[str, str]] = {}           # Google round-trip code -> email
    verifiers: ClassVar[list[str]] = []
    switched_on: ClassVar[dict[str, bool]] = {}

    @classmethod
    def reset(cls):
        cls.passwords = {u.email: "right password" for u in (OFFICIAL, MEMBER, OTHER_CHAMA, GONE, NO_PHONE)}
        cls.texts, cls.verifiers = [], []
        cls.google_codes = {"g-member": MEMBER.email, "g-official": OFFICIAL.email, "g-stranger": "who@example.com"}
        cls.switched_on = {"google": True, "phone": True}

    def sign_in(self, email, password):
        if self.passwords.get(email) != password:
            raise ApiError(401, "bad_credentials", "That email and password do not match.", field="password")
        return auth.Identity(id=f"sb-{email}", email=email)

    def providers(self):
        return dict(self.switched_on)

    def google_url(self, redirect_to, challenge):
        return ("https://sb.example/auth/v1/authorize?provider=google"
                f"&redirect_to={redirect_to}&code_challenge={challenge}")

    def exchange_code(self, code, verifier):
        self.verifiers.append(verifier)
        if code not in self.google_codes:
            raise ApiError(401, "google_failed", "Signing in with Google did not finish.")
        email = self.google_codes[code]
        return auth.Identity(id=f"sb-{email}", email=email)

    def send_code(self, phone):
        self.texts.append(phone)

    def verify_code(self, phone, code):
        if code != RIGHT_CODE:
            raise ApiError(401, "bad_code", "That code is not right, or it has expired.", field="code")
        return auth.Identity(id=f"sb-phone-{phone}", email="", phone=phone)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("TWO_STEP_FOR_OFFICIALS", "true")
    monkeypatch.setenv("WEB_LOG_DIR", str(tmp_path))
    web_settings.cache_clear()
    FakeSupabase.reset()
    store = FakeStore()
    for name in ("by_email", "by_phone", "by_id", "link_identity", "link_phone_identity", "start_session", "session",
                 "end_session", "start_step", "step", "count_attempt", "end_step"):
        monkeypatch.setattr(users_data, name, getattr(store, name))
    monkeypatch.setattr(session, "member_names", lambda conn, chama: {"M-aaaa1111": "Alvin Wise"})
    monkeypatch.setattr(officials.early_warning, "overview", lambda conn, chama: {"chama": chama})
    monkeypatch.setattr(officials.early_warning, "member_page", lambda conn, chama, code: {"code": code})
    monkeypatch.setattr(officials.records, "is_member_of", lambda conn, chama, code: code.startswith(chama))

    from chama.web.app import create_app

    app = create_app()

    def no_database():
        yield None

    app.dependency_overrides[connection] = no_database
    app.dependency_overrides[auth.supabase_auth] = FakeSupabase
    with TestClient(app) as c:
        c.store = store
        yield c
    web_settings.cache_clear()


def sign_in(client, user: User):
    """Password, then for an official the texted code."""
    response = client.post("/api/session", json={"email": user.email, "password": "right password"})
    assert response.status_code == 200, response.text
    if user.is_official:
        assert response.json() == {"next": "code", "phone_hint": f"the phone ending {user.phone[-3:]}"}
        response = client.post("/api/session/code", json={"code": RIGHT_CODE})
        assert response.status_code == 200, response.text
    return response


def csrf(client) -> dict:
    return {"x-csrf-token": client.cookies.get(auth.CSRF_COOKIE)}


def test_sign_in_sets_an_httponly_session_and_a_csrf_cookie(client):
    response = sign_in(client, OFFICIAL)
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith(auth.SESSION_COOKIE))
    csrf_cookie = next(c for c in cookies if c.startswith(auth.CSRF_COOKIE))
    assert "HttpOnly" in session_cookie and "SameSite=lax" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert response.json()["user"] == {
        "name": "Alvin Muriithi", "role": "official", "position": "treasurer", "chama_id": "chama_demo",
        "chama_name": "Humble Sister", "member_code": None,
    }
    token = client.cookies.get(auth.SESSION_COOKIE)
    assert token not in client.store.sessions            # only the hash is stored
    assert auth.hash_token(token) in client.store.sessions


def test_wrong_password_is_refused_next_to_the_field(client):
    response = client.post("/api/session", json={"email": OFFICIAL.email, "password": "wrong"})
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["field"] == "password" and error["ref"].startswith("R-")


def test_missing_email_is_refused_next_to_the_field(client):
    response = client.post("/api/session", json={"email": "", "password": "x"})
    assert response.status_code == 422 and response.json()["error"]["field"] == "email"


def test_an_unknown_or_deactivated_account_gets_no_session(client):
    client.store.accounts.pop(OFFICIAL.email)
    FakeSupabase.passwords["new@example.com"] = "right password"
    for email in ("new@example.com", GONE.email):
        response = client.post("/api/session", json={"email": email, "password": "right password"})
        assert response.status_code == 403 and response.json()["error"]["code"] == "no_access"
    assert client.store.sessions == {}


def test_without_a_session_every_page_says_the_session_ended(client):
    for path in ("/api/me", "/api/overview", "/api/members/chama_demo-1"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Your session ended. Sign in again to carry on."


def test_signing_out_ends_the_session(client):
    sign_in(client, OFFICIAL)
    assert client.get("/api/me").status_code == 200
    assert client.delete("/api/session").status_code == 200
    assert client.get("/api/me").status_code == 401


def test_changes_need_the_sessions_csrf_token(client):
    from fastapi import APIRouter

    sign_in(client, OFFICIAL)
    router = APIRouter()

    @router.post("/api/test-change")
    def change(user: auth.Official) -> dict:
        return {"ok": True}

    client.app.include_router(router)
    assert client.post("/api/test-change").json()["error"]["code"] == "csrf"
    assert client.post("/api/test-change", headers={"x-csrf-token": "forged"}).status_code == 403
    assert client.post("/api/test-change", headers=csrf(client)).json() == {"ok": True}


def test_changes_from_another_site_are_refused(client):
    response = client.post("/api/session", json={"email": OFFICIAL.email, "password": "right password"},
                           headers={"origin": "https://evil.example"})
    assert response.status_code == 403 and response.json()["error"]["code"] == "origin"


def test_a_member_gets_not_allowed_on_officials_routes(client):
    sign_in(client, MEMBER)
    assert client.get("/api/me").json()["user"]["name"] == "Alvin Wise"
    for path in ("/api/overview", "/api/members", "/api/members/chama_demo-1"):
        response = client.get(path)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "not_allowed"


def test_an_official_sees_only_their_own_chamas_members(client):
    sign_in(client, OTHER_CHAMA)
    assert client.get("/api/overview").json() == {"chama": "chama_b"}   # from the account, not the URL
    assert client.get("/api/members/chama_demo-1").status_code == 403
    assert client.get("/api/members/chama_b-1").json() == {"code": "chama_b-1"}


def test_demo_mode_keeps_a_real_officials_name_off_screen(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    web_settings.cache_clear()
    sign_in(client, OTHER_CHAMA)                     # chama_b is a real chama
    me = client.get("/api/me").json()
    assert me["user"]["name"] == "Chair" and me["demo_mode"] is True


def test_errors_never_show_a_stack_trace(client, monkeypatch):
    def broken(conn, chama):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(officials.early_warning, "overview", broken)
    sign_in(client, OFFICIAL)
    with TestClient(client.app, raise_server_exceptions=False) as c:
        c.cookies = client.cookies
        response = c.get("/api/overview")
    assert response.status_code == 500
    body = response.json()["error"]
    assert "secret" not in body["message"] and body["ref"] in body["message"]


# ---- D-037: the texted code, phone sign-in and Google ---------------------------------


def test_an_officials_password_alone_opens_nothing_until_the_texted_code(client):
    response = client.post("/api/session", json={"email": OFFICIAL.email, "password": "right password"})
    assert response.json() == {"next": "code", "phone_hint": "the phone ending 001"}
    assert FakeSupabase.texts == [OFFICIAL.phone]
    assert auth.SESSION_COOKIE not in client.cookies and client.store.sessions == {}
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/session/step").json() == {"waiting": True, "method": "password",
                                                      "phone_hint": "the phone ending 001"}
    assert client.post("/api/session/code", json={"code": RIGHT_CODE}).status_code == 200
    assert client.get("/api/me").json()["user"]["role"] == "official"
    assert client.store.linked[OFFICIAL.id] == {"email": f"sb-{OFFICIAL.email}", "phone": f"sb-phone-{OFFICIAL.phone}"}
    assert client.get("/api/session/step").json() == {"waiting": False}   # the code is used once


def test_wrong_codes_are_counted_and_the_fifth_ends_the_sign_in(client):
    client.post("/api/session", json={"email": OFFICIAL.email, "password": "right password"})
    for left in (4, 3, 2, 1):
        response = client.post("/api/session/code", json={"code": "000000"})
        assert response.status_code == 401
        error = response.json()["error"]
        assert error["field"] == "code" and f"({left} tr" in error["message"]
    response = client.post("/api/session/code", json={"code": "000000"})
    assert response.json()["error"]["code"] == "step_ended"
    assert client.post("/api/session/code", json={"code": RIGHT_CODE}).json()["error"]["code"] == "step_ended"
    assert client.store.sessions == {}


def test_a_code_must_have_six_digits(client):
    client.post("/api/session", json={"email": OFFICIAL.email, "password": "right password"})
    response = client.post("/api/session/code", json={"code": "12 34"})
    assert response.status_code == 422 and response.json()["error"]["field"] == "code"


def test_an_official_without_a_phone_is_told_to_ask_for_one(client):
    response = client.post("/api/session", json={"email": NO_PHONE.email, "password": "right password"})
    assert response.status_code == 403 and response.json()["error"]["code"] == "no_phone"
    assert FakeSupabase.texts == []


def test_with_the_second_step_off_an_official_signs_in_with_the_password(client, monkeypatch):
    monkeypatch.setenv("TWO_STEP_FOR_OFFICIALS", "false")
    web_settings.cache_clear()
    response = client.post("/api/session", json={"email": NO_PHONE.email, "password": "right password"})
    assert response.json()["user"]["role"] == "official" and FakeSupabase.texts == []


def test_a_member_signs_in_with_a_phone_and_the_texted_code(client):
    response = client.post("/api/session/phone", json={"phone": "0700 000 002"})
    assert response.json() == {"next": "code", "phone_hint": "the phone ending 002"}
    assert FakeSupabase.texts == [MEMBER.phone]
    me = client.post("/api/session/code", json={"code": RIGHT_CODE}).json()
    assert me["user"]["name"] == "Alvin Wise" and me["user"]["role"] == "member"
    assert client.store.linked[MEMBER.id] == {"phone": f"sb-phone-{MEMBER.phone}"}


@pytest.mark.parametrize("phone, code", [
    ("0700 000 009", "no_access"),          # no account: nothing is texted, so nobody pays for strangers' texts
    ("0700000004", "no_access"),            # a deactivated account
    ("0700000001", "official_phone"),       # officials start with Google or a password
    ("12345", "phone_invalid"),
])
def test_phone_sign_in_texts_only_numbers_with_a_members_account(client, phone, code):
    response = client.post("/api/session/phone", json={"phone": phone})
    assert response.json()["error"]["code"] == code and response.json()["error"]["field"] == "phone"
    assert FakeSupabase.texts == []


def test_resend_texts_the_same_phone_again(client):
    client.post("/api/session/phone", json={"phone": "0700000002"})
    assert client.post("/api/session/code/resend").json()["sent"] is True
    assert FakeSupabase.texts == [MEMBER.phone, MEMBER.phone]


def test_a_code_without_a_waiting_sign_in_is_refused(client):
    response = client.post("/api/session/code", json={"code": RIGHT_CODE})
    assert response.status_code == 401 and response.json()["error"]["code"] == "step_ended"


def test_google_goes_through_supabase_with_a_pkce_challenge(client):
    response = client.get("/api/session/google?next=/m/loans", follow_redirects=False)
    assert response.status_code == 303
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["redirect_to"] == ["http://testserver/api/session/google/callback"] or query["redirect_to"] == [
        "http://localhost:3000/api/session/google/callback"]
    cookie = next(c for c in response.headers.get_list("set-cookie") if c.startswith(auth.PKCE_COOKIE))
    assert "HttpOnly" in cookie and "Path=/api/session/google" in cookie
    verifier = client.cookies.get(auth.PKCE_COOKIE).strip('"').split("|")[0]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert query["code_challenge"] == [challenge]


def test_back_from_google_a_member_lands_on_their_page(client):
    client.get("/api/session/google?next=/m/loans", follow_redirects=False)
    sent = client.cookies.get(auth.PKCE_COOKIE).strip('"').split("|")[0]
    response = client.get("/api/session/google/callback?code=g-member", follow_redirects=False)
    assert response.headers["location"] == "/m/loans"
    assert FakeSupabase.verifiers == [sent]                 # the code is exchanged with this browser's verifier
    assert client.get("/api/me").json()["user"]["role"] == "member"


def test_back_from_google_an_official_still_types_the_code(client):
    client.get("/api/session/google", follow_redirects=False)
    response = client.get("/api/session/google/callback?code=g-official", follow_redirects=False)
    assert response.headers["location"] == "/signin?step=code"
    assert client.get("/api/me").status_code == 401 and FakeSupabase.texts == [OFFICIAL.phone]
    assert client.post("/api/session/code", json={"code": RIGHT_CODE}).json()["user"]["role"] == "official"


@pytest.mark.parametrize("query, error", [
    ("code=g-stranger", "no_access"),        # a Google account with no chama account
    ("code=unknown", "google_failed"),
    ("error=access_denied", "google_failed"),
])
def test_google_problems_come_back_to_the_sign_in_page(client, query, error):
    client.get("/api/session/google", follow_redirects=False)
    response = client.get(f"/api/session/google/callback?{query}", follow_redirects=False)
    assert response.headers["location"] == f"/signin?error={error}"
    assert client.store.sessions == {}


def test_google_without_the_browsers_verifier_is_refused(client):
    response = client.get("/api/session/google/callback?code=g-member", follow_redirects=False)
    assert response.headers["location"] == "/signin?error=google_failed" and FakeSupabase.verifiers == []


def test_the_sign_in_page_hears_which_ways_are_switched_on(client):
    FakeSupabase.switched_on = {"google": False, "phone": True}
    site = client.get("/api/site").json()
    assert site["methods"] == {"password": web_settings().supabase_ready, "google": False, "phone": True}
    assert site["officials_confirm_by_phone"] is True
    response = client.get("/api/session/google", follow_redirects=False)
    assert response.headers["location"] == "/signin?error=google_off"


@pytest.mark.parametrize("written, expected", [
    ("0712 345 678", "+254712345678"),
    ("0112345678", "+254112345678"),
    ("712345678", "+254712345678"),
    ("254712345678", "+254712345678"),
    ("+254 712-345-678", "+254712345678"),
    ("00254712345678", "+254712345678"),
    ("+447700900123", "+447700900123"),
    ("0812345678", None),
    ("07123", None),
    ("phone", None),
    ("", None),
])
def test_phone_numbers_are_read_as_kenyan_numbers(written, expected):
    assert auth.normalise_phone(written) == expected
