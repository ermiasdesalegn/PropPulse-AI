"""Wrapper around google-genai SDK with multi-key rotation and free-tier quota failover."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
import threading
import time
from typing import Any, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

RETRYABLE_CODES = {429, 500, 503}


def load_keys_from_file(filepath: str | Path) -> list[str]:
    """Loads API keys from a CSV or line-delimited text file."""
    path = Path(filepath)
    if not path.is_file():
        return []

    keys: list[str] = []
    try:
        with open(path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                first_cell = row[0].strip()
                if not first_cell or first_cell.startswith("#"):
                    continue
                if first_cell.lower() in {"api_key", "key", "gemini_key", "token"}:
                    continue
                keys.append(first_cell)
    except Exception as exc:
        log.warning("Failed to load Gemini API keys from %s: %s", path, exc)

    deduped: list[str] = []
    for k in keys:
        if k and k not in deduped:
            deduped.append(k)
    return deduped


def mask_key(key: str) -> str:
    """Mask key for safe logging (e.g. AIza...4x1z)."""
    if not key:
        return "<empty>"
    if len(key) <= 8:
        return key[:2] + "..." + key[-2:]
    return key[:4] + "..." + key[-4:]


class Gemini:
    def __init__(
        self,
        api_key: str | list[str] | None = None,
        model: str = "gemini-3.8-flash",
        api_keys: list[str] | str | None = None,
        keys_file: str | Path | None = None,
        max_retries: int = 4,
    ):
        self.model = model
        self.max_retries = max_retries
        self._lock = threading.Lock()
        self._client_cache: dict[str, genai.Client] = {}

        resolved_keys: list[str] = []

        if api_key:
            if isinstance(api_key, list):
                resolved_keys.extend(api_key)
            elif isinstance(api_key, str):
                if "," in api_key:
                    resolved_keys.extend(k.strip() for k in api_key.split(",") if k.strip())
                elif api_key.strip():
                    resolved_keys.append(api_key.strip())

        if api_keys:
            if isinstance(api_keys, list):
                resolved_keys.extend(api_keys)
            elif isinstance(api_keys, str):
                resolved_keys.extend(k.strip() for k in api_keys.split(",") if k.strip())

        if keys_file:
            resolved_keys.extend(load_keys_from_file(keys_file))

        self.keys: list[str] = []
        for k in resolved_keys:
            cleaned = k.strip()
            if cleaned and cleaned not in self.keys:
                self.keys.append(cleaned)

        if not self.keys:
            raise ValueError("No valid Gemini API keys provided. Provide api_key, api_keys, or a keys_file.")

        self.current_index = 0
        self.rotation_count = 0
        self.last_rotation: dict | None = None
        log.info(
            "Initialized Gemini with %d API key(s) (Active: #1 %s, model: %s)",
            len(self.keys),
            mask_key(self.keys[0]),
            self.model,
        )

    @property
    def key_count(self) -> int:
        return len(self.keys)

    @property
    def current_key(self) -> str:
        with self._lock:
            return self.keys[self.current_index]

    @property
    def status(self) -> dict:
        with self._lock:
            return {
                "total_keys": len(self.keys),
                "active_index": self.current_index + 1,
                "active_key": mask_key(self.keys[self.current_index]),
                "rotation_count": self.rotation_count,
                "last_rotation": self.last_rotation,
            }

    def _get_client_for_key(self, key: str) -> genai.Client:
        client = self._client_cache.get(key)
        if client is None:
            client = genai.Client(api_key=key)
            self._client_cache[key] = client
        return client

    def get_current_client(self) -> tuple[genai.Client, str, int]:
        with self._lock:
            idx = self.current_index
            key = self.keys[idx]
            client = self._get_client_for_key(key)
            return client, key, idx

    def rotate_key(self, failed_key: str | None = None) -> int:
        """Rotates to the next API key. If failed_key is passed, only rotate if that key is still active."""
        with self._lock:
            if failed_key and self.keys[self.current_index] != failed_key:
                return self.current_index

            old_idx = self.current_index
            self.current_index = (self.current_index + 1) % len(self.keys)
            self.rotation_count += 1
            self.last_rotation = {
                "from_index": old_idx + 1,
                "from_key": mask_key(self.keys[old_idx]),
                "to_index": self.current_index + 1,
                "to_key": mask_key(self.keys[self.current_index]),
                "time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            }
            log.warning(
                "Rotating Gemini API Key: #%d (%s) -> #%d (%s) [Total rotations: %d]",
                old_idx + 1,
                mask_key(self.keys[old_idx]),
                self.current_index + 1,
                mask_key(self.keys[self.current_index]),
                self.rotation_count,
            )
            return self.current_index

    def generate(self, contents: Any, config: types.GenerateContentConfig) -> types.GenerateContentResponse:
        delay = 2.0
        keys_count = max(len(self.keys), 1)
        total_attempts = keys_count * (self.max_retries + 1)

        for attempt in range(total_attempts):
            client, key, idx = self.get_current_client()
            try:
                return client.models.generate_content(model=self.model, contents=contents, config=config)
            except errors.APIError as exc:
                err_str = str(exc)
                is_quota = exc.code == 429 or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower()
                is_auth_error = exc.code in {401, 403} and (
                    "API_KEY" in err_str.upper() or "INVALID" in err_str.upper()
                )
                is_retryable = exc.code in RETRYABLE_CODES or is_quota or is_auth_error

                if not is_retryable:
                    raise

                should_rotate = (is_quota or is_auth_error) and len(self.keys) > 1

                if should_rotate:
                    self.rotate_key(failed_key=key)
                else:
                    log.warning(
                        "Gemini %s on key #%d (%s) (attempt %d/%d) — retrying in %.0fs",
                        exc.code,
                        idx + 1,
                        mask_key(key),
                        attempt + 1,
                        total_attempts,
                        delay,
                    )

                if attempt == total_attempts - 1:
                    log.error("Gemini exhausted all %d API key(s) and retries.", len(self.keys))
                    raise

                if should_rotate and ((attempt + 1) % len(self.keys) != 0):
                    time.sleep(0.05)
                else:
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

