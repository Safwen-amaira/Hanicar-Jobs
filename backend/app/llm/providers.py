"""LLM provider interface. App must work with AI fully off."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import wrap_untrusted
from app.models import LlmRequest


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def complete(self, prompt: str, *, system: str = "") -> str:
        raise NotImplementedError


class MockProvider(LLMProvider):
    name = "mock"

    async def complete(self, prompt: str, *, system: str = "") -> str:
        return (
            "[MockProvider] AI is off or mocked. "
            "Draft generated from templates only.\n\n"
            f"System hint: {system[:120]}\n"
            f"Prompt digest: {hashlib.sha256(prompt.encode()).hexdigest()[:12]}"
        )


class OpenAICompatibleProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def complete(self, prompt: str, *, system: str = "") -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system or "You are a careful career assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def complete(self, prompt: str, *, system: str = "") -> str:
        payload = {
            "model": self.model,
            "prompt": f"{system}\n\n{prompt}" if system else prompt,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"{self.base_url}/api/generate", json=payload)
            r.raise_for_status()
            return r.json().get("response", "")


class KaggleProvider(LLMProvider):
    """Placeholder for Kaggle notebook / kernel backed inference. Falls back to mock when offline."""

    name = "kaggle"

    async def complete(self, prompt: str, *, system: str = "") -> str:
        return (
            "[KaggleProvider] No live Kaggle kernel configured. "
            "Falling back to template mode. Enable a notebook endpoint to use this provider."
        )


def get_provider() -> LLMProvider:
    settings = get_settings()
    if not settings.ai_enabled:
        return MockProvider()
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return OpenAICompatibleProvider(
            settings.openai_api_key, settings.openai_base_url, settings.openai_model
        )
    if provider == "ollama":
        return OllamaProvider(settings.ollama_base_url, settings.ollama_model)
    if provider == "kaggle":
        return KaggleProvider()
    return MockProvider()


class CachedLLM:
    def __init__(self, session: AsyncSession, provider: Optional[LLMProvider] = None):
        self.session = session
        self.provider = provider or get_provider()
        self.prompt_version = "v1"

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        untrusted_label: str = "CONTENT",
        untrusted_body: str = "",
    ) -> str:
        if untrusted_body:
            prompt = f"{prompt}\n\n{wrap_untrusted(untrusted_label, untrusted_body)}"
        model = getattr(self.provider, "model", self.provider.name)
        if hasattr(self.provider, "model"):
            model = self.provider.model  # type: ignore[attr-defined]
        else:
            model = self.provider.name
        input_hash = hashlib.sha256(f"{system}||{prompt}".encode()).hexdigest()
        cached = await self.session.scalar(
            select(LlmRequest).where(
                LlmRequest.input_hash == input_hash,
                LlmRequest.model == model,
                LlmRequest.prompt_version == self.prompt_version,
            )
        )
        if cached:
            return cached.response
        response = await self.provider.complete(prompt, system=system)
        self.session.add(
            LlmRequest(
                input_hash=input_hash,
                model=model,
                prompt_version=self.prompt_version,
                response=response,
            )
        )
        await self.session.flush()
        return response
