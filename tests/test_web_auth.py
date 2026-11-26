"""Google sign-in, sessions, CSRF and role checks without a database."""
from __future__ import annotations

import base64
import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from typing import ClassVar
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
import httpx

from chama.web import auth
from chama.web.data import users as users_data
from chama.web.data.users import User
from chama.web.db import connection
from chama.web.errors import ApiError
from chama.web.routes import officials, session
from chama.web.settings import web_settings

OFFICIAL = User(1, "alvin@example.com", "official", "chama_demo", None, "Alvin Muriithi", "treasurer", True,
                phone="+254700000001")
MEMBER = User(2, "wise@example.com", "member", "chama_demo", "M-aaaa1111", None, None, True,
              phone="+254700000002")
OTHER_CHAMA = User(3, "other@example.com", "official", "chama_b", None, "Someone", "chair", True)
GONE = User(4, "gone@example.com", "official", "chama_demo", None, "Gone", None, False)


class FakeStore:
    def __init__(self):
        self.accounts = {u.email.casefold(): u for u in (OFFICIAL, MEMBER, OTHER_CHAMA, GONE)}
        self.sessions: dict[str, tuple[int, str, datetime, bool]] = {}

    def by_email(self, conn, email):
        return self.accounts.get(email.strip().casefold())

    def by_id(self, conn, user_id):
        return next((u for u in self.accounts.values() if u.id == user_id), None)

    def link_identity(self, conn, user_id, identity_id):
        user = self.by_id(conn, user_id)
        if user and user.identity_id is None:
            self.accounts[user.email.casefold()] = replace(user, identity_id=identity_id)

    def start_session(self, conn, token_hash, user_id, csrf, expires_at):
        self.sessions[token_hash] = (user_id, csrf, expires_at, True)

    def session(self, conn, token_hash):
        found = self.sessions.get(token_hash)
        if not found or not found[3] or found[2] <= datetime.now(timezone.utc):
            return None
        user = self.by_id(conn, found[0])
        return (user, found[1]) if user and user.active else None

    def end_session(self, conn, token_hash):
        if token_hash in self.sessions:
            user_id, csrf, expires, _ = self.sessions[token_hash]
            self.sessions[token_hash] = (user_id, csrf, expires, False)


class FakeSupabase:
    google_codes: ClassVar[dict[str, tuple[str, str]]] = {}
    verifiers: ClassVar[list[str]] = []
    google_enabled: ClassVar[bool] = True

    @classmethod
    def reset(cls):
        cls.google_codes = {
            "g-member": (MEMBER.email, "sb-member"),
            "g-official": (OFFICIAL.email, "sb-official"),
            "g-stranger": ("stranger@example.com", "sb-stranger"),
            "g-mismatch": ("wise@example.com", "sb-other-identity"),
        }
        cls.verifiers = []
        cls.google_enabled = True

    def providers(self):
        return {"google": self.google_enabled}

    def google_url(self, redirect_to, challenge):
        from urllib.parse import urlencode
        return "https://sb.example/auth/v1/authorize?" + urlencode({
            "provider": "google", "redirect_to": redirect_to,
            "code_challenge": challenge, "code_challenge_method": "s256",
        })

    def exchange_code(self, code, verifier):
        self.verifiers.append(verifier)
        if code not in self.google_codes:
            raise ApiError(401, "google_failed", "Google sign-in failed.")
        email, identity_id = self.google_codes[code]
        return auth.Identity(id=identity_id, email=email)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.example")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "public-test-key")
    monkeypatch.setenv("WEB_LOG_DIR", str(tmp_path))
    web_settings.cache_clear()
    FakeSupabase.reset()
    store = FakeStore()
    for name in ("by_email", "by_id", "link_identity", "start_session", "session", "end_session"):
        monkeypatch.setattr(users_data, name, getattr(store, name))
    monkeypatch.setattr(session, "member_names", lambda conn, chama: {"M-aaaa1111": "Alvin Wise"})
    monkeypatch.setattr(officials.early_warning, "overview", lambda conn, chama, lang: {"chama": chama})
    monkeypatch.setattr(officials.early_warning, "member_page", lambda conn, chama, code, lang: {"code": code})
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


def begin_google(client, next_page=""):
    url = "/api/session/google" + (f"?next={next_page}" if next_page else "")
    return client.get(url, follow_redirects=False)


def callback(client, code):
    return client.get(f"/api/session/google/callback?code={code}", follow_redirects=False)


def signed_in(client, email):
    begin_google(client)
    return callback(client, "g-member" if email == MEMBER.email else "g-official")


def csrf(client):
    return {"x-csrf-token": client.cookies.get(auth.CSRF_COOKIE)}


def test_google_oauth_uses_supabase_and_server_side_pkce(client):
    response = begin_google(client, "/m/loans")
    assert response.status_code == 303
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["provider"] == ["google"]
    assert query["code_challenge_method"] == ["s256"]
    # Unknown Host headers fall back to the first configured public origin.
    assert query["redirect_to"] == ["http://localhost:3000/api/session/google/callback"]
    cookie = next(c for c in response.headers.get_list("set-cookie") if c.startswith(auth.PKCE_COOKIE))
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/api/session/google" in cookie
    verifier = client.cookies.get(auth.PKCE_COOKIE).strip('"').split("|")[0]
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert query["code_challenge"] == [expected]


@pytest.mark.parametrize("code,role,landing", [
    ("g-member", "member", "/m"),
    ("g-official", "official", "/o"),
])
def test_existing_active_member_and_official_sign_in_without_sms(client, code, role, landing):
    begin_google(client)
    response = callback(client, code)
    assert response.status_code == 303 and response.headers["location"] == landing
    assert client.get("/api/me").json()["user"]["role"] == role
    assert client.store.sessions


def test_pkce_verifier_is_used_once_for_exchange(client):
    begin_google(client)
    verifier = client.cookies.get(auth.PKCE_COOKIE).strip('"').split("|")[0]
    callback(client, "g-member")
    assert FakeSupabase.verifiers == [verifier]


@pytest.mark.parametrize("code,error", [("g-stranger", "no_access"), ("unknown", "google_failed")])
def test_unknown_google_accounts_and_bad_codes_get_no_session(client, code, error):
    begin_google(client)
    response = callback(client, code)
    assert response.headers["location"] == f"/signin?error={error}"
    assert not client.store.sessions


def test_inactive_account_gets_no_session(client):
    FakeSupabase.google_codes["g-gone"] = (GONE.email, "sb-gone")
    begin_google(client)
    assert callback(client, "g-gone").headers["location"] == "/signin?error=no_access"


def test_google_email_must_match_the_account_selected_by_backend(client, monkeypatch):
    # Simulate a malformed/misbehaving account lookup returning the wrong row.
    monkeypatch.setattr(users_data, "by_email", lambda conn, email: OFFICIAL)
    begin_google(client)
    response = callback(client, "g-member")
    assert response.headers["location"] == "/signin?error=mismatch"
    assert not client.store.sessions


def test_existing_google_identity_cannot_be_silently_replaced(client):
    client.store.accounts[MEMBER.email] = replace(MEMBER, identity_id="previous-google-id")
    begin_google(client)
    response = callback(client, "g-member")
    assert response.headers["location"] == "/signin?error=mismatch"
    assert client.store.accounts[MEMBER.email].identity_id == "previous-google-id"
    assert not client.store.sessions


def test_first_google_sign_in_links_identity_and_opens_session(client):
    begin_google(client)
    callback(client, "g-member")
    assert client.store.accounts[MEMBER.email].identity_id == "sb-member"
    assert client.store.sessions


def test_session_cookie_is_http_only_and_csrf_cookie_is_readable(client):
    begin_google(client)
    response = callback(client, "g-official")
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith(auth.SESSION_COOKIE))
    csrf_cookie = next(c for c in cookies if c.startswith(auth.CSRF_COOKIE))
    assert "HttpOnly" in session_cookie and "SameSite=lax" in session_cookie
    assert "HttpOnly" not in csrf_cookie and "SameSite=lax" in csrf_cookie
    token = client.cookies.get(auth.SESSION_COOKIE)
    assert token not in client.store.sessions
    assert auth.hash_token(token) in client.store.sessions
    assert "Max-Age=43200" in session_cookie


def test_production_session_cookie_is_secure(client, monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "true")
    web_settings.cache_clear()
    begin_google(client)
    response = callback(client, "g-official")
    session_cookie = next(c for c in response.headers.get_list("set-cookie") if c.startswith(auth.SESSION_COOKIE))
    assert "Secure" in session_cookie and "HttpOnly" in session_cookie


def test_password_and_phone_auth_routes_are_not_available(client):
    assert client.post("/api/session", json={"email": OFFICIAL.email, "password": "ignored"}).status_code == 405
    assert client.post("/api/session/phone", json={"phone": OFFICIAL.phone}).status_code == 404
    assert client.post("/api/session/code", json={"code": "123456"}).status_code == 404
    assert not client.store.sessions


def test_logout_ends_server_session(client):
    signed_in(client, OFFICIAL.email)
    assert client.get("/api/me").status_code == 200
    assert client.delete("/api/session", headers=csrf(client)).json() == {"signed_out": True}
    assert client.get("/api/me").status_code == 401


def test_csrf_protects_changes(client):
    from fastapi import APIRouter
    signed_in(client, OFFICIAL.email)
    router = APIRouter()
    @router.post("/api/test-change")
    def change(user: auth.Official) -> dict:
        return {"ok": True}
    client.app.include_router(router)
    assert client.post("/api/test-change").json()["error"]["code"] == "csrf"
    assert client.post("/api/test-change", headers={"x-csrf-token": "forged"}).status_code == 403
    assert client.post("/api/test-change", headers=csrf(client)).json() == {"ok": True}


def test_expired_session_is_rejected(client):
    signed_in(client, MEMBER.email)
    token = client.cookies.get(auth.SESSION_COOKIE)
    key = auth.hash_token(token)
    user_id, csrf_token, _, active = client.store.sessions[key]
    client.store.sessions[key] = (user_id, csrf_token, datetime.now(timezone.utc), active)
    assert client.get("/api/me").status_code == 401


def test_role_authorization_is_based_on_database_account(client):
    signed_in(client, MEMBER.email)
    assert client.get("/api/me").json()["user"]["role"] == "member"
    assert client.get("/api/overview").status_code == 403


def test_official_is_scoped_to_their_database_chama(client):
    FakeSupabase.google_codes["g-other"] = (OTHER_CHAMA.email, "sb-other")
    begin_google(client)
    callback(client, "g-other")
    assert client.get("/api/overview").json() == {"chama": "chama_b"}
    assert client.get("/api/members/chama_demo-1").status_code == 403


def test_site_and_frontend_contract_report_google_only(client):
    site_body = client.get("/api/site").json()
    assert site_body == {"demo_mode": False, "sign_in_ready": True, "methods": {"google": True}}
    FakeSupabase.google_enabled = False
    assert client.get("/api/site").json()["methods"] == {"google": False}
    assert begin_google(client).headers["location"] == "/signin?error=google_off"


def test_callback_without_pkce_cookie_is_rejected(client):
    assert callback(client, "g-member").headers["location"] == "/signin?error=google_failed"
    assert not FakeSupabase.verifiers


def test_changes_from_another_origin_are_refused(client):
    signed_in(client, OFFICIAL.email)
    response = client.delete("/api/session", headers={**csrf(client), "origin": "https://evil.example"})
    assert response.status_code == 403 and response.json()["error"]["code"] == "origin"


def test_google_sign_in_can_be_disabled_when_supabase_is_not_configured(client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "")
    web_settings.cache_clear()
    assert client.get("/api/site").json()["methods"] == {"google": False}


@pytest.mark.parametrize("written,expected", [
    ("0712 345 678", "+254712345678"), ("0112345678", "+254112345678"),
    ("712345678", "+254712345678"), ("254712345678", "+254712345678"),
    ("+254 712-345-678", "+254712345678"), ("00254712345678", "+254712345678"),
    ("+447700900123", "+447700900123"), ("0812345678", None), ("07123", None),
    ("phone", None), ("", None),
])
def test_phone_numbers_remain_normalizable_for_account_data_and_reminders(written, expected):
    assert auth.normalise_phone(written) == expected


def test_supabase_provider_probe_reports_google_availability_only(monkeypatch):
    settings = replace(web_settings(), supabase_url="https://supabase.example", supabase_key="public-test-key")
    monkeypatch.setattr(auth, "_PROVIDERS", {})
    def handler(request):
        assert request.url.path == "/auth/v1/settings"
        assert request.headers["apikey"] == "public-test-key"
        return httpx.Response(200, json={"external": {"google": True, "phone": True, "email": True}})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert auth.SupabaseAuth(settings, client=client).providers() == {"google": True}


def test_supabase_code_exchange_uses_pkce_verifier():
    settings = replace(web_settings(), supabase_url="https://supabase.example", supabase_key="public-test-key")
    verifier = "a-pkce-verifier"
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/auth/v1/token"
        assert request.url.params["grant_type"] == "pkce"
        assert request.headers["apikey"] == "public-test-key"
        assert request.read().decode() == (
            '{"auth_code":"oauth-code","code_verifier":"a-pkce-verifier"}'
        )
        return httpx.Response(200, json={"user": {"id": "google-user-id", "email": "member@example.com"}})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    identity = auth.SupabaseAuth(settings, client=client).exchange_code("oauth-code", verifier)
    assert identity == auth.Identity(id="google-user-id", email="member@example.com")
