"""Sign-in, sessions, CSRF and role checks (X1, X2, R1-R4), without a database.

The account and session queries are replaced by an in-memory store and
Supabase by a fake, so every rule of auth.py is checked on its own.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient

from chama.web import auth
from chama.web.data import users as users_data
from chama.web.data.users import User
from chama.web.db import connection
from chama.web.errors import ApiError
from chama.web.routes import officials, session
from chama.web.settings import web_settings

OFFICIAL = User(1, "grace@example.com", "official", "chama_demo", None, "Grace Achieng", "treasurer", True)
MEMBER = User(2, "neema@example.com", "member", "chama_demo", "M-aaaa1111", None, None, True)
OTHER_CHAMA = User(3, "other@example.com", "official", "chama_b", None, "Someone", "chair", True)
GONE = User(4, "gone@example.com", "official", "chama_demo", None, "Gone", None, False)


class FakeStore:
    def __init__(self):
        self.accounts = {u.email: u for u in (OFFICIAL, MEMBER, OTHER_CHAMA, GONE)}
        self.sessions: dict[str, tuple[int, str, bool]] = {}

    def by_email(self, conn, email):
        return self.accounts.get(email.strip().lower())

    def link_identity(self, conn, user_id, identity_id):
        pass

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


class FakeSupabase:
    passwords: ClassVar[dict[str, str]] = {u.email: "right password" for u in (OFFICIAL, MEMBER, OTHER_CHAMA, GONE)}

    def sign_in(self, email, password):
        if self.passwords.get(email) != password:
            raise ApiError(401, "bad_credentials", "That email and password do not match.", field="password")
        return auth.Identity(id=f"sb-{email}", email=email)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("DEMO_MODE", "false")
    web_settings.cache_clear()
    store = FakeStore()
    for name in ("by_email", "link_identity", "start_session", "session", "end_session"):
        monkeypatch.setattr(users_data, name, getattr(store, name))
    monkeypatch.setattr(session, "member_names", lambda conn, chama: {"M-aaaa1111": "Neema Kiprono"})
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
    response = client.post("/api/session", json={"email": user.email, "password": "right password"})
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
        "name": "Grace Achieng", "role": "official", "position": "treasurer", "chama_id": "chama_demo",
        "chama_name": "Tumaini Women's Group", "member_code": None,
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
    assert client.get("/api/me").json()["user"]["name"] == "Neema Kiprono"
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
