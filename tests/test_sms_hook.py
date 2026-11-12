"""Supabase's Send SMS hook, texted through Africa's Talking (D-042).

Supabase's signature is made here the way Standard Webhooks makes it; Africa's
Talking is a fake transport, so nothing is sent anywhere.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from chama.web.data import users as users_data
from chama.web.data.users import User
from chama.web.db import connection
from chama.web.routes import hooks
from chama.web.services import sms_hook
from chama.web.settings import web_settings

KEY = b"0123456789abcdef0123456789abcdef"
SECRET = "v1,whsec_" + base64.b64encode(KEY).decode()
MEMBER = User(2, "wise@example.com", "member", "chama_demo", "M-aaaa1111", None, None, True, phone="+254700000002")
GONE = User(4, "gone@example.com", "official", "chama_demo", None, "Gone", None, False, phone="+254700000004")


def signed(payload: dict, stamp: int | None = None, key: bytes = KEY) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode()
    stamp = stamp or int(time.time())
    signature = base64.b64encode(hmac.new(key, f"msg_1.{stamp}.".encode() + body, hashlib.sha256).digest()).decode()
    return body, {"webhook-id": "msg_1", "webhook-timestamp": str(stamp), "webhook-signature": f"v1,{signature}",
                  "content-type": "application/json"}


def payload(phone="+254700000002", code="123456"):
    return {"user": {"id": "sb-1", "phone": phone}, "sms": {"otp": code}}


class FakeAT:
    """Africa's Talking: records each request and answers with `answer`."""

    def __init__(self, status=201, answer=None):
        self.requests, self.status = [], status
        self.answer = answer if answer is not None else {"SMSMessageData": {"Message": "Sent to 1/1 Total Cost: KES 0.8000",
            "Recipients": [{"statusCode": 101, "number": "+254700000002", "status": "Success",
                            "cost": "KES 0.8000", "messageId": "ATXid_1"}]}}

    def client(self) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return httpx.Response(self.status, json=self.answer)
        return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def hook(monkeypatch, tmp_path):
    monkeypatch.setenv("WEB_LOG_DIR", str(tmp_path))
    web_settings.cache_clear()
    accounts = {u.phone: u for u in (MEMBER, GONE)}
    monkeypatch.setattr(users_data, "by_phone", lambda conn, phone: accounts.get(phone))
    fake = FakeAT()

    from chama.web.app import create_app

    app = create_app()

    def no_database():
        yield None

    settings = {"value": sms_hook.SmsSettings(SECRET, "kibaba", "at-key", "KIBABA")}
    app.dependency_overrides[connection] = no_database
    app.dependency_overrides[hooks.sms_settings] = lambda: settings["value"]
    app.dependency_overrides[hooks.sms_client] = lambda: fake.client()
    with TestClient(app) as client:
        client.fake, client.settings = fake, settings
        yield client
    web_settings.cache_clear()


def post(client, body, headers):
    return client.post("/api/hooks/send-sms", content=body, headers=headers)


def test_a_signed_code_for_a_member_is_texted(hook):
    response = post(hook, *signed(payload()))
    assert response.status_code == 200 and response.json() == {}
    (request,) = hook.fake.requests
    assert str(request.url) == sms_hook.LIVE_URL
    assert request.headers["apiKey"] == "at-key" and request.headers["Accept"] == "application/json"
    form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
    assert form["username"] == "kibaba" and form["to"] == "+254700000002" and form["from"] == "KIBABA"
    assert "123456" in form["message"] and form["message"].startswith("Kibaba:")


def test_the_sandbox_username_uses_the_sandbox(hook):
    hook.settings["value"] = sms_hook.SmsSettings(SECRET, "sandbox", "sandbox-key")
    assert post(hook, *signed(payload(phone="254700000002"))).status_code == 200   # a number without +
    form = parse_qs(hook.fake.requests[0].content.decode())
    assert str(hook.fake.requests[0].url) == sms_hook.SANDBOX_URL
    assert form["to"] == ["+254700000002"] and "from" not in form


@pytest.mark.parametrize("change", ["wrong_key", "old", "unsigned", "altered"])
def test_an_unsigned_old_or_altered_request_texts_nothing(hook, change):
    body, headers = signed(payload(), key=b"another key 0123456789abcdefghi") if change == "wrong_key" else \
        signed(payload(), stamp=int(time.time()) - 600) if change == "old" else signed(payload())
    if change == "unsigned":
        headers.pop("webhook-signature")
    if change == "altered":
        body = body.replace(b"123456", b"654321")
    response = post(hook, body, headers)
    assert response.status_code == 401
    assert set(response.json()["error"]) == {"http_code", "message"}
    assert hook.fake.requests == []


@pytest.mark.parametrize("phone", ["+254799999999", "+254700000004"], ids=["no-account", "deactivated"])
def test_only_numbers_with_an_active_account_are_texted(hook, phone):
    response = post(hook, *signed(payload(phone=phone)))
    assert response.status_code == 403 and hook.fake.requests == []


def test_an_africas_talking_refusal_is_reported_to_supabase(hook):
    hook.fake.answer = {"SMSMessageData": {"Message": "Sent to 0/1", "Recipients": [
        {"statusCode": 405, "number": "+254700000002", "status": "InsufficientBalance", "cost": "0"}]}}
    response = post(hook, *signed(payload()))
    assert response.status_code == 500
    assert "InsufficientBalance (405)" in response.json()["error"]["message"]


def test_a_bad_api_key_is_reported_to_supabase(hook):
    hook.fake.status, hook.fake.answer = 401, {"error": "The supplied authentication is invalid"}
    response = post(hook, *signed(payload()))
    assert response.status_code == 500 and "refused the request (401)" in response.json()["error"]["message"]


def test_without_settings_it_says_what_to_add(hook):
    hook.settings["value"] = sms_hook.SmsSettings("", "", "")
    message = post(hook, *signed(payload())).json()["error"]["message"]
    assert "SMS_HOOK_SECRET" in message and hook.fake.requests == []


def test_the_code_never_reaches_the_log(hook, caplog):
    with caplog.at_level(logging.INFO, logger="chama.web"):
        post(hook, *signed(payload(code="987654")))
        post(hook, *signed(payload(phone="+254799999999", code="987654")))
    text = caplog.text
    assert "987654" not in text and "254700000002" not in text and "ending 002" in text


@pytest.mark.parametrize("body", [{"user": {}, "sms": {"otp": "123456"}}, {"user": {"phone": "+254700000002"},
                                                                          "sms": {"otp": "12ab"}}])
def test_a_payload_without_a_number_or_code_texts_nothing(hook, body):
    assert post(hook, *signed(body)).status_code == 400 and hook.fake.requests == []
