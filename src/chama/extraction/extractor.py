"""Read one prepared ledger photo with a vision model through the Claude API.

The answer is structured output (schema.LedgerPage), so it always has the raw
layout's fields. It is still a draft: checks.py flags lines to look at and a
person reviews the rows before they are loaded (decision D-024). The API key
is read from ANTHROPIC_API_KEY in .env and stays on the server.
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass

import anthropic
import pydantic

from chama import StepFailed
from chama.extraction.prompt import SYSTEM_PROMPT, USER_PROMPT
from chama.extraction.schema import LedgerPage


class ExtractionFailed(StepFailed):
    """The model gave no usable answer; the message says why and what to do."""


@dataclass
class Extraction:
    page: LedgerPage
    model: str  # the model that answered (a fallback model if the first declined)
    seconds: float
    input_tokens: int
    output_tokens: int


class ClaudeExtractor:
    """Settings come from `extraction` in config/pipeline.yaml."""

    def __init__(self, settings: dict, client: anthropic.Anthropic | None = None):
        self.model = settings["model"]
        self.effort = settings["effort"]
        self.max_tokens = settings["max_tokens"]
        self._client = client

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def extract(self, jpeg: bytes) -> Extraction:
        start = time.perf_counter()
        image = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.standard_b64encode(jpeg).decode("ascii"),
            },
        }
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": [image, {"type": "text", "text": USER_PROMPT}]}],
                output_format=LedgerPage,
                output_config={"effort": self.effort},
                # If the model declines, the API retries on its recommended fallback model.
                extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
                extra_body={"fallbacks": "default"},
            )
        except anthropic.AuthenticationError as e:
            raise ExtractionFailed("The Anthropic API key was rejected: check ANTHROPIC_API_KEY in .env.") from e
        except anthropic.RateLimitError as e:
            raise ExtractionFailed("The extraction service is busy (rate limit). Try again in a minute.") from e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                raise ExtractionFailed("The extraction service is unavailable. Try again shortly.") from e
            raise ExtractionFailed(f"The extraction request was refused: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise ExtractionFailed("Could not reach the extraction service. Check the internet connection.") from e
        except (pydantic.ValidationError, ValueError) as e:
            raise ExtractionFailed(
                "The model's answer could not be read as a ledger page. If it was cut off, "
                "raise extraction.max_tokens; otherwise try again."
            ) from e

        if response.stop_reason == "refusal":
            raise ExtractionFailed("The model declined to read this photo.")
        if response.stop_reason == "max_tokens":
            raise ExtractionFailed(
                "The answer was cut off before the end of the page. Raise extraction.max_tokens."
            )
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
