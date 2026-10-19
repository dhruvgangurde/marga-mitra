"""The one door to a language model. Returns None when there is no model, on a timeout or on a bad answer, so callers always have a fallback."""
from __future__ import annotations

import asyncio
import base64
import functools
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic
from google import genai
from google.genai import types
from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from contracts.interfaces import LLMClient

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _media_type(image: bytes) -> str:
    return "image/png" if image.startswith(PNG_MAGIC) else "image/jpeg"


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "none"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "claude-haiku-5-5"
    vision_model: str = "claude-sonnet-5-5"
    copilot_model: str = "claude-sonnet-5-5"
    llm_cache: bool = True


def llm_settings() -> LLMSettings:
    return LLMSettings()


class NoLLM:
    provider = "none"

    async def structured[T: BaseModel](self, system: str, user: str, schema: type[T], model: str | None = None,
                                       images: list[bytes] | None = None, max_tokens: int = 800) -> T | None:
        return None


class ProviderClient:
    provider = ""

    def __init__(self, api_key: SecretStr, model: str, cache_dir: Path | None, timeout_s: float = 25.0) -> None:
        self.api_key = api_key
        self.model = model
        self.cache_dir = cache_dir
        self.timeout_s = timeout_s

    async def structured[T: BaseModel](self, system: str, user: str, schema: type[T], model: str | None = None,
                                       images: list[bytes] | None = None, max_tokens: int = 800) -> T | None:
        used_model = model or self.model
        imgs = images or []
        path = self._cache_path(system, user, schema, used_model, imgs, max_tokens)
        cached = self._read_cache(path, schema)
        if cached is not None:
            return cached
        try:
            out = await asyncio.wait_for(self._call(system, user, schema, used_model, imgs, max_tokens), self.timeout_s)
        except Exception:  # timeout, network, API or validation: the caller falls back
            return None
        if not isinstance(out, schema):
            return None
        self._write_cache(path, out)
        return out

    async def _call(self, system: str, user: str, schema: type[BaseModel], model: str, images: list[bytes],
                    max_tokens: int) -> Any:
        raise NotImplementedError

    def _cache_path(self, system: str, user: str, schema: type[BaseModel], model: str, images: list[bytes],
                    max_tokens: int) -> Path | None:
        if self.cache_dir is None:
            return None
        key = hashlib.sha256(json.dumps({
            "provider": self.provider, "model": model, "system": system, "user": user, "schema": schema.__name__,
            "fields": schema.model_json_schema(), "images": [hashlib.sha256(i).hexdigest() for i in images],
            "max_tokens": max_tokens,
        }, sort_keys=True).encode()).hexdigest()
        return self.cache_dir / f"{key}.json"

    @staticmethod
    def _read_cache[T: BaseModel](path: Path | None, schema: type[T]) -> T | None:
        if path is None or not path.exists():
            return None
        try:
            return schema.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):  # a broken file counts as a miss
            return None

    @staticmethod
    def _write_cache(path: Path | None, out: BaseModel) -> None:
        if path is None:
            return
        tmp = path.with_name(path.name + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(out.model_dump_json(), encoding="utf-8")
            os.replace(tmp, path)
        except OSError:  # the cache only saves credits; the answer is still good
            return


class AnthropicClient(ProviderClient):
    provider = "anthropic"

    async def _call(self, system: str, user: str, schema: type[BaseModel], model: str, images: list[bytes],
                    max_tokens: int) -> Any:
        content: Any = user
        if images:
            blocks: list[dict[str, Any]] = [
                {"type": "image", "source": {"type": "base64", "media_type": _media_type(i),
                                             "data": base64.b64encode(i).decode("ascii")}}
                for i in images
            ]
            content = [*blocks, {"type": "text", "text": user}]
        async with AsyncAnthropic(api_key=self.api_key.get_secret_value(), timeout=20, max_retries=1) as client:
            resp = await client.messages.parse(model=model, max_tokens=max_tokens, system=system,
                                               messages=[{"role": "user", "content": content}], output_format=schema)
        return resp.parsed_output


class GeminiClient(ProviderClient):
    provider = "gemini"

    async def _call(self, system: str, user: str, schema: type[BaseModel], model: str, images: list[bytes],
                    max_tokens: int) -> Any:
        parts: list[Any] = [types.Part.from_bytes(data=i, mime_type=_media_type(i)) for i in images]
        parts.append(user)
        config = types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                             response_schema=schema, max_output_tokens=max_tokens)
        async with genai.Client(api_key=self.api_key.get_secret_value()).aio as client:
            resp = await client.models.generate_content(model=model, contents=parts, config=config)
        return resp.parsed


@functools.cache
def get_llm() -> LLMClient:
    s = llm_settings()
    cache_dir = Path(".cache/llm") if s.llm_cache else None
    key = s.llm_api_key.get_secret_value()
    if s.llm_provider == "anthropic" and key:
        return AnthropicClient(s.llm_api_key, s.llm_model, cache_dir)
    if s.llm_provider == "gemini" and key:
        return GeminiClient(s.llm_api_key, s.llm_model, cache_dir)
    return NoLLM()
