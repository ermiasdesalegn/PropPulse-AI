"""Thin wrapper around the google-genai SDK with free-tier friendly retries."""

from __future__ import annotations

import logging
import time
from typing import Any, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

RETRYABLE_CODES = {429, 500, 503}


class Gemini:
    def __init__(self, api_key: str, model: str, max_retries: int = 4):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.max_retries = max_retries

    def generate(self, contents: Any, config: types.GenerateContentConfig) -> types.GenerateContentResponse:
        delay = 2.0
        for attempt in range(self.max_retries + 1):
            try:
                return self.client.models.generate_content(model=self.model, contents=contents, config=config)
            except errors.APIError as exc:
                if exc.code not in RETRYABLE_CODES or attempt == self.max_retries:
                    raise
                log.warning("Gemini %s (attempt %d) — retrying in %.0fs", exc.code, attempt + 1, delay)
                time.sleep(delay)
                delay = min(delay * 2, 30)
        raise RuntimeError("unreachable")

    def text(self, prompt: str, system: str | None = None, temperature: float = 0.7) -> str:
        config = types.GenerateContentConfig(system_instruction=system, temperature=temperature)
        return (self.generate(prompt, config).text or "").strip()

    def structured(self, prompt: str, schema: type[T], system: str | None = None) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=schema,
        )
        response = self.generate(prompt, config)
        if isinstance(response.parsed, schema):
            return response.parsed
        return schema.model_validate_json(response.text or "{}")
