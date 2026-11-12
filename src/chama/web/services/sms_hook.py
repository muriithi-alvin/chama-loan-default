"""Supabase's sign-in codes, texted through Africa's Talking (D-042).

Supabase supports Twilio, MessageBird, Vonage and TextLocal for texts, but a
Twilio trial cannot send them and Twilio costs about US$0.31 a text to Kenya.
Africa's Talking is a Kenyan provider at well under a shilling a text. Supabase
reaches it through its Send SMS hook: instead of texting, Supabase POSTs each
code here, signed with a secret (Standard Webhooks), and this sends it.

    Supabase  --signed {user.phone, sms.otp}-->  POST /api/hooks/send-sms
              --form: username, to, message, from-->  Africa's Talking

Checks before anything is sent:
- the signature, with SMS_HOOK_SECRET ("v1,whsec_<base64>" from Supabase),
  made within the last 5 minutes (a copied request cannot be sent again later);
- the number belongs to an active Kibaba account, so nobody can make the chama
  pay for texts to other numbers, even with the Supabase key.

The code is never written to a log; numbers appear as their last three digits.
Supabase gives a hook 5 seconds, so Africa's Talking gets 4.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass

import httpx

log = logging.getLogger("chama.web")

LIVE_URL = "https://api.africastalking.com/version1/messaging"
SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"
TOLERANCE_S = 300                     # Standard Webhooks: a signature older than 5 minutes is refused
SENT = {100, 101, 102}                # Processed, Sent, Queued
MESSAGE = "Kibaba: your sign-in code is {code}. Never share it, even with a chama official."


class HookRefused(Exception):
    """The hook did not send the text: a status and a message for Supabase's log."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class SmsSettings:
    hook_secret: str          # SMS_HOOK_SECRET, from Supabase: v1,whsec_<base64>
    username: str             # AFRICASTALKING_USERNAME ("sandbox" for the test environment)
    api_key: str              # AFRICASTALKING_API_KEY
    sender_id: str = ""       # AFRICASTALKING_SENDER_ID, once Africa's Talking has approved one

    @property
    def ready(self) -> bool:
        return bool(self.hook_secret and self.username and self.api_key)

    @property
    def url(self) -> str:
        return SANDBOX_URL if self.username == "sandbox" else LIVE_URL


def _key(secret: str) -> bytes:
    raw = secret.strip()
    for prefix in ("v1,", "whsec_"):
        raw = raw.removeprefix(prefix)
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as e:
        raise HookRefused(500, "SMS_HOOK_SECRET is not the secret Supabase gave (v1,whsec_...).") from e


def verify(secret: str, headers, body: bytes, now: float | None = None) -> dict:
    """The hook's payload, once its Standard Webhooks signature is right and recent."""
    msg_id = headers.get("webhook-id")
    stamp = headers.get("webhook-timestamp")
    signatures = headers.get("webhook-signature")
    if not (msg_id and stamp and signatures):
        raise HookRefused(401, "The request is not signed.")
    try:
        age = abs((now if now is not None else time.time()) - int(stamp))
    except ValueError as e:
        raise HookRefused(401, "The signature's time is not a number.") from e
    if age > TOLERANCE_S:
        raise HookRefused(401, "The signature is too old or from the future.")
    expected = base64.b64encode(hmac.new(_key(secret), f"{msg_id}.{stamp}.".encode() + body,
                                         hashlib.sha256).digest()).decode()
    for part in signatures.split():
        version, _, signature = part.partition(",")
        if version == "v1" and hmac.compare_digest(signature, expected):
            try:
                return json.loads(body)
            except ValueError as e:
                raise HookRefused(400, "The payload is not JSON.") from e
    raise HookRefused(401, "The signature does not match.")


def phone_and_code(payload: dict) -> tuple[str, str]:
    phone = "".join(ch for ch in str((payload.get("user") or {}).get("phone") or "") if ch.isdigit())
    code = str((payload.get("sms") or {}).get("otp") or "")
    if len(phone) < 8 or not (len(code) == 6 and code.isdigit()):
        raise HookRefused(400, "The payload has no phone number or no 6-digit code.")
    return "+" + phone, code


def send(settings: SmsSettings, phone: str, code: str, client: httpx.Client | None = None) -> dict:
    """Text the code; Africa's Talking's answer for the one recipient."""
    form = {"username": settings.username, "to": phone, "message": MESSAGE.format(code=code), "bulkSMSMode": "1"}
    if settings.sender_id:
        form["from"] = settings.sender_id
    try:
        response = (client or httpx.Client(timeout=4)).post(
            settings.url, data=form, headers={"apiKey": settings.api_key, "Accept": "application/json"})
    except httpx.HTTPError as e:
        raise HookRefused(500, f"Africa's Talking did not answer ({type(e).__name__}).") from e
    if response.status_code >= 300:
        raise HookRefused(500, f"Africa's Talking refused the request ({response.status_code}): "
                               f"{response.text[:200]}")
    try:
        recipients = response.json()["SMSMessageData"]["Recipients"]
    except (ValueError, KeyError, TypeError) as e:
        raise HookRefused(500, f"Africa's Talking gave an unexpected answer: {response.text[:200]}") from e
    if not recipients:
        message = (response.json().get("SMSMessageData") or {}).get("Message", "no recipients")
        raise HookRefused(500, f"Africa's Talking sent nothing: {message}")
    first = recipients[0]
    if int(first.get("statusCode", 0)) not in SENT:
        raise HookRefused(500, f"Africa's Talking did not send it: {first.get('status')} ({first.get('statusCode')})")
    return first


def handle(settings: SmsSettings, headers, body: bytes, has_account, client: httpx.Client | None = None) -> None:
    """Verify, check the number has an account, send. Raises HookRefused when nothing was sent."""
    if not settings.ready:
        raise HookRefused(500, "Texting is not set up: add SMS_HOOK_SECRET, AFRICASTALKING_USERNAME and "
                               "AFRICASTALKING_API_KEY (docs/web_setup.md).")
    phone, code = phone_and_code(verify(settings.hook_secret, headers, body))
    if not has_account(phone):
        log.warning("sms hook: no active account for the number ending %s; nothing sent", phone[-3:])
        raise HookRefused(403, "This number has no active Kibaba account, so no text was sent.")
    sent = send(settings, phone, code, client)
    log.info("sms hook: code sent to the number ending %s (%s, %s)", phone[-3:], sent.get("status"),
             sent.get("cost", "cost not given"))
