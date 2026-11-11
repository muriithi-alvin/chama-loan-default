"""Read one prepared ledger photo with a vision model.

Two kinds of provider, chosen under `extraction` in config/pipeline.yaml:
- `openai_compatible`: any service with an OpenAI-style chat completions API.
  The default is Groq's free plan with the open-weight Qwen 3.8 27B model.
- `claude`: the Claude API (paid), kept for comparison (decisions D-024, D-025).
Both return the page as structured output in the raw layout (schema.py). It is
still a draft: checks.py flags lines to look at and a person reviews the rows
before they are loaded. API keys are read from .env and stay on the server.
"""
from __future__ import annotations

import base64
import os
import ssl
import time
from dataclasses import dataclass

import anthropic
import httpx
import pydantic

from chama import StepFailed
from chama.extraction.prompt import SYSTEM_PROMPT, USER_PROMPT
from chama.extraction.schema import LedgerPage, page_schema, repaired_page


class ExtractionFailed(StepFailed):
    """The model gave no usable answer; the message says why and what to do.

    `transient` is true for a rate limit, a timeout or the service being down:
    trying again later may work (the web worker retries these).
    """

    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient


@dataclass
class Extraction:
    page: LedgerPage
    model: str  # the model that answered
    seconds: float
    input_tokens: int
    output_tokens: int


CUT_OFF = "The answer was cut off before the end of the page. Raise max_tokens for this provider."
UNREADABLE = ("The model's answer could not be read as a ledger page. If it was cut off, "
              "raise max_tokens for this provider; otherwise try again.")


def _base64(jpeg: bytes) -> str:
    return base64.standard_b64encode(jpeg).decode("ascii")


def user_text(notes: str = "") -> str:
    """The usual instructions, plus notes about one chama's book when it has its
    own layout (`reading_notes` in config/pipeline.yaml). Chama B has none, so its
    pages are read exactly as before."""
    notes = notes.strip()
    return f"{USER_PROMPT}\n\nNotes about this chama's book:\n{notes}" if notes else USER_PROMPT


def tls_context() -> ssl.SSLContext:
    """TLS with the usual certificate checks, offering only the X25519 key exchange.

    OpenSSL 3.5 also offers a post-quantum key share by default, which makes
    the first handshake message bigger than one network packet. Some networks
    drop it on the way to Groq: from 24 Oct 2026 every read timed out here,
    while curl, which offers X25519, still connected.
    """
    context = ssl.create_default_context()
    context.set_ecdh_curve("X25519")
    return context


class OpenAICompatibleExtractor:
    """A provider with an OpenAI-style chat completions API, such as Groq.

    Settings: base_url, api_key_env (the .env variable holding the key), model,
    max_tokens and request_options (extra request fields, e.g. reasoning_effort).
    """

    def __init__(self, settings: dict, client: httpx.Client | None = None):
        self.base_url = settings["base_url"].rstrip("/")
        self.api_key_env = settings["api_key_env"]
        self.model = settings["model"]
        self.max_tokens = settings["max_tokens"]
        self.options = settings.get("request_options") or {}
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=180, verify=tls_context())
        return self._client

    def extract(self, jpeg: bytes, notes: str = "") -> Extraction:
        key = os.getenv(self.api_key_env, "").strip()
        if not key:
            raise ExtractionFailed(f"{self.api_key_env} is missing from .env.")
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": user_text(notes)},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + _base64(jpeg)}},
                ]},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "ledger_page", "schema": page_schema()},
            },
            **self.options,
        }
        start = time.perf_counter()
        try:
            response = self.client.post(f"{self.base_url}/chat/completions", json=body,
                                        headers={"Authorization": f"Bearer {key}"})
        except httpx.RequestError as e:
            raise ExtractionFailed(
                "Could not reach the extraction service. Check the internet connection.",
                transient=True,
            ) from e
        if response.status_code != 200:
            raise ExtractionFailed(_http_problem(response, self.api_key_env),
                                   transient=response.status_code == 429 or response.status_code >= 500)

        data = response.json()
        choice = data["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ExtractionFailed(CUT_OFF)
        content = choice["message"].get("content") or ""
        try:
            page = LedgerPage.model_validate_json(content)
        except pydantic.ValidationError as e:
            page = repaired_page(content)
            if page is None:
                raise ExtractionFailed(UNREADABLE) from e
        usage = data.get("usage") or {}
        return Extraction(
            page=page,
            model=data.get("model", self.model),
            seconds=round(time.perf_counter() - start, 1),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )


def _http_problem(response: httpx.Response, key_env: str) -> str:
    """A short, safe explanation of a failed request (the key is never shown)."""
    try:
        detail = (response.json().get("error") or {}).get("message", "")
    except ValueError:
        detail = response.text[:200]
    status = response.status_code
    if status in (401, 403):
        return f"The API key was rejected: check {key_env} in .env."
    if status == 429:
        wait = response.headers.get("retry-after")
        return ("The extraction service's rate limit was reached. "
                + (f"Try again in {wait} s." if wait else "Try again in a minute."))
    if status == 413:
        return f"The request is too large for the plan's limits: {detail}"
    if status >= 500:
        return "The extraction service is unavailable. Try again shortly."
    return f"The extraction request was refused ({status}): {detail}"


class ClaudeExtractor:
    """The Claude API. Settings: model, effort, max_tokens; key ANTHROPIC_API_KEY."""

    def __init__(self, settings: dict, client: anthropic.Anthropic | None = None):
        self.model = settings["model"]
        self.effort = settings["effort"]
        self.max_tokens = settings["max_tokens"]
        self._client = client

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            try:
                self._client = anthropic.Anthropic()
            except anthropic.AnthropicError as e:
                raise ExtractionFailed("ANTHROPIC_API_KEY is missing from .env.") from e
        return self._client

    def extract(self, jpeg: bytes, notes: str = "") -> Extraction:
        start = time.perf_counter()
        image = {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": _base64(jpeg)},
        }
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": [image, {"type": "text", "text": user_text(notes)}]}],
                output_format=LedgerPage,
                output_config={"effort": self.effort},
                # If the model declines, the API retries on its recommended fallback model.
                extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
                extra_body={"fallbacks": "default"},
            )
        except anthropic.AuthenticationError as e:
            raise ExtractionFailed("The Anthropic API key was rejected: check ANTHROPIC_API_KEY in .env.") from e
        except anthropic.RateLimitError as e:
            raise ExtractionFailed("The extraction service is busy (rate limit). Try again in a minute.",
                                   transient=True) from e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                raise ExtractionFailed("The extraction service is unavailable. Try again shortly.",
                                       transient=True) from e
            raise ExtractionFailed(f"The extraction request was refused: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise ExtractionFailed("Could not reach the extraction service. Check the internet connection.",
                                   transient=True) from e
        except (pydantic.ValidationError, ValueError) as e:
            raise ExtractionFailed(UNREADABLE) from e

        if response.stop_reason == "refusal":
            raise ExtractionFailed("The model declined to read this photo.")
        if response.stop_reason == "max_tokens":
            raise ExtractionFailed(CUT_OFF)
        page = response.parsed_output
        if page is None:
            raise ExtractionFailed("The model returned no ledger page. Try again.")
        return Extraction(
            page=page,
            model=response.model,
            seconds=round(time.perf_counter() - start, 1),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


EXTRACTORS = {"openai_compatible": OpenAICompatibleExtractor, "claude": ClaudeExtractor}


def provider_settings(settings: dict, provider: str | None = None) -> tuple[str, dict]:
    """(name, settings) of the chosen provider: `provider`, else extraction.provider."""
    name = provider or settings["provider"]
    if name not in settings["providers"]:
        known = ", ".join(settings["providers"])
        raise StepFailed(f"No extraction provider '{name}' in config/pipeline.yaml (known: {known}).")
    return name, settings["providers"][name]


def make_extractor(settings: dict, provider: str | None = None):
    """The extractor for the chosen provider."""
    name, options = provider_settings(settings, provider)
    kind = options.get("kind")
    if kind not in EXTRACTORS:
        raise StepFailed(f"Extraction provider '{name}' has an unknown kind '{kind}'.")
    return EXTRACTORS[kind](options)
