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

FALLBACK_PREFIXES = ("[MockProvider]", "[KaggleProvider]", "[LLMError]")
PROVIDER_ERROR_MARKERS = (
    "reached its budget",
    "enospc",
    "rate limit",
    "please migrate",
    "api key used for this request",
    "invalid api key",
    "insufficient_quota",
    "a valid api key is required",
    "unauthorized",
    "no space left on device",
    "model is required",
    "no endpoints found",  # OpenRouter no-key error
    "requires a valid api key",
)


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def complete(self, prompt: str, *, system: str = "") -> str:
        raise NotImplementedError


def is_fallback_text(text: str) -> bool:
    value = (text or "").lstrip()
    if not value:
        return True
    if any(value.startswith(prefix) for prefix in FALLBACK_PREFIXES):
        return True
    lowered = value.lower()
    return any(marker in lowered for marker in PROVIDER_ERROR_MARKERS)


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

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        *,
        use_responses_api: bool = False,
        reasoning_effort: str = "medium",
        provider_name: str = "openai",
        allow_anonymous: bool = False,
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.use_responses_api = use_responses_api
        self.reasoning_effort = reasoning_effort
        self.name = provider_name
        self.allow_anonymous = allow_anonymous
        self.timeout = timeout

    async def complete(self, prompt: str, *, system: str = "") -> str:
        if not self.api_key and not self.allow_anonymous:
            return f"[MockProvider] {self.name} API key is not configured. Falling back to template mode."
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            if self.use_responses_api and "api.openai.com" in self.base_url:
                payload = {
                    "model": self.model,
                    "instructions": system or "You are a careful career assistant.",
                    "input": prompt,
                    "reasoning": {"effort": self.reasoning_effort},
                }
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    r = await client.post(f"{self.base_url}/responses", json=payload, headers=headers)
                    r.raise_for_status()
                    data = r.json()
                    if data.get("output_text"):
                        return data["output_text"]
                    chunks: list[str] = []
                    for item in data.get("output", []):
                        for content in item.get("content", []):
                            if content.get("type") in {"output_text", "text"} and content.get("text"):
                                chunks.append(content["text"])
                    return "\n".join(chunks).strip()
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system or "You are a careful career assistant."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            return f"[LLMError] {self.name} request failed: {exc}. Using template mode."


class GroqProvider(OpenAICompatibleProvider):
    name = "groq"

    def __init__(self, api_key: str, base_url: str, model: str):
        super().__init__(
            api_key,
            base_url,
            model,
            use_responses_api=False,
            provider_name="groq",
            timeout=45.0,
        )


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter.ai – offers genuinely free LLM inference with a free API key.

    Free models: meta-llama/llama-3.2-3b-instruct:free,
                 mistralai/mistral-7b-instruct:free,
                 google/gemma-3-4b-it:free

    Sign up at https://openrouter.ai and grab a free key – no billing required.
    """

    name = "openrouter"

    def __init__(self, api_key: str, base_url: str, model: str):
        super().__init__(
            api_key,
            base_url,
            model,
            use_responses_api=False,
            provider_name="openrouter",
            timeout=60.0,
        )

    async def complete(self, prompt: str, *, system: str = "") -> str:
        if not self.api_key:
            return "[MockProvider] OpenRouter API key not set. Get a free key at openrouter.ai."
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://hanicar.jobs",
            "X-Title": "Hanicar Jobs",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system or "You are a careful career assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                r.raise_for_status()
                data = r.json()
                text = _chat_message_text(data)
                if text and not is_fallback_text(text):
                    return text
                # Some free models return a usage/error block instead
                err = (data.get("error") or {}).get("message", "")
                return f"[LLMError] openrouter: {err or 'empty response'}. Using template mode."
        except Exception as exc:
            return f"[LLMError] openrouter request failed: {exc}. Using template mode."


def _chat_message_text(data: dict) -> str:
    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            chunks = [part.get("text", "") for part in content if isinstance(part, dict)]
            joined = "".join(chunks).strip()
            if joined:
                return joined
    if data.get("response"):
        return str(data["response"]).strip()
    if data.get("output_text"):
        return str(data["output_text"]).strip()
    return ""


class PollinationsProvider(LLMProvider):
    """Anonymous free text API. Fail fast so the cascade can use local Ollama."""

    name = "pollinations"

    def __init__(self, endpoint: str, model: str, api_key: str = ""):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key

    async def complete(self, prompt: str, *, system: str = "") -> str:
        headers = {
            "Content-Type": "application/json",
            "Referer": "https://hanicar.jobs",
            "User-Agent": "HanicarJobs/0.2",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system or "You are a careful career assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "referrer": "hanicar-jobs",
        }
        last_error = ""
        try:
            async with httpx.AsyncClient(timeout=18.0) as client:
                r = await client.post(self.endpoint, json=payload, headers=headers)
                body = r.text
                if r.is_success:
                    try:
                        text = _chat_message_text(r.json())
                    except Exception:
                        text = body.strip()
                    if text and not is_fallback_text(text):
                        return text
                    last_error = text or body[:240]
                else:
                    last_error = body[:240]
                simple = (f"{system}\n{prompt}" if system else prompt).replace("\n", " ")[:800]
                get = await client.get(
                    f"https://text.pollinations.ai/{simple}",
                    params={"model": self.model},
                    headers={"User-Agent": "HanicarJobs/0.2", "Referer": "https://hanicar.jobs"},
                )
                if get.is_success and get.text.strip() and not is_fallback_text(get.text):
                    return get.text.strip()
                last_error = last_error or get.text[:240]
        except Exception as exc:
            last_error = str(exc)
        return f"[LLMError] pollinations request failed: {last_error}. Using template mode."


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def complete(self, prompt: str, *, system: str = "") -> str:
        if not self.api_key:
            return "[MockProvider] Gemini API key is not configured. Falling back to template mode."
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(url, params={"key": self.api_key}, json=payload)
                r.raise_for_status()
                data = r.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            return "".join(part.get("text", "") for part in parts).strip()
        except Exception as exc:
            return f"[LLMError] gemini request failed: {exc}. Using template mode."


_OLLAMA_READY: set[str] = set()


class OllamaProvider(LLMProvider):
    """Local free LLM. Pulls the configured model on first use."""

    name = "ollama"

    def __init__(self, base_url: str, model: str, auto_pull: bool = True):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.auto_pull = auto_pull

    async def complete(self, prompt: str, *, system: str = "") -> str:
        try:
            await self._ensure_model()
            async with httpx.AsyncClient(timeout=180.0) as client:
                r = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "stream": False,
                        "messages": [
                            {"role": "system", "content": system or "You are a careful career assistant."},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                r.raise_for_status()
                data = r.json()
            text = ((data.get("message") or {}).get("content")) or data.get("response") or ""
            if not str(text).strip():
                return "[LLMError] ollama returned an empty draft. Using template mode."
            return str(text).strip()
        except Exception as exc:
            return f"[LLMError] ollama request failed: {exc}. Using template mode."

    async def _ensure_model(self) -> None:
        key = f"{self.base_url}:{self.model}"
        if key in _OLLAMA_READY:
            return
        async with httpx.AsyncClient(timeout=20.0) as client:
            tags = await client.get(f"{self.base_url}/api/tags")
            tags.raise_for_status()
            names = [item.get("name", "") for item in (tags.json().get("models") or [])]
            if self.model in names or any(name.startswith(f"{self.model}") for name in names):
                _OLLAMA_READY.add(key)
                return
        if not self.auto_pull:
            raise RuntimeError(f"ollama model {self.model} is not installed")
        async with httpx.AsyncClient(timeout=600.0) as client:
            pull = await client.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model, "stream": False},
            )
            pull.raise_for_status()
        _OLLAMA_READY.add(key)


class KaggleProvider(LLMProvider):
    """Placeholder for Kaggle notebook / kernel backed inference. Falls back to mock when offline."""

    name = "kaggle"

    async def complete(self, prompt: str, *, system: str = "") -> str:
        return (
            "[KaggleProvider] No live Kaggle kernel configured. "
            "Falling back to template mode. Enable a notebook endpoint to use this provider."
        )


class CascadeProvider(LLMProvider):
    """Try live providers in order; keep Mock last. Sending is never this provider's job."""

    name = "auto"

    def __init__(self, providers: list[LLMProvider]):
        self.providers = providers
        self.last_used: LLMProvider | None = None

    @property
    def model(self) -> str:
        provider = self.last_used or (self.providers[0] if self.providers else MockProvider())
        return str(getattr(provider, "model", provider.name))

    async def complete(self, prompt: str, *, system: str = "") -> str:
        last = ""
        for provider in self.providers:
            result = await provider.complete(prompt, system=system)
            if not is_fallback_text(result):
                self.last_used = provider
                self.name = provider.name
                return result
            last = result
        return last or "[LLMError] No live LLM responded. Using template mode."


def _configured_providers() -> list[LLMProvider]:
    settings = get_settings()
    groq_key = settings.groq_api_key or (
        settings.openai_api_key if "groq.com" in (settings.openai_base_url or "") else ""
    )
    providers: list[LLMProvider] = []
    if groq_key:
        providers.append(GroqProvider(groq_key, settings.groq_base_url, settings.groq_model))
    if settings.gemini_api_key:
        providers.append(GeminiProvider(settings.gemini_api_key, settings.gemini_model))
    if settings.openrouter_api_key:
        providers.append(
            OpenRouterProvider(
                settings.openrouter_api_key,
                settings.openrouter_base_url,
                settings.openrouter_model,
            )
        )
    if settings.openai_api_key and "groq.com" not in (settings.openai_base_url or ""):
        providers.append(
            OpenAICompatibleProvider(
                settings.openai_api_key,
                settings.openai_base_url,
                settings.openai_model,
                use_responses_api=settings.openai_use_responses_api,
                reasoning_effort=settings.openai_reasoning_effort,
            )
        )
    providers.append(
        OllamaProvider(
            settings.ollama_base_url,
            settings.ollama_model,
            auto_pull=settings.ollama_auto_pull,
        )
    )
    providers.append(
        PollinationsProvider(
            settings.pollinations_base_url,
            settings.pollinations_model,
            settings.pollinations_api_key,
        )
    )
    return providers


def get_provider() -> LLMProvider:
    settings = get_settings()
    if not settings.ai_enabled:
        return MockProvider()
    requested = settings.llm_provider.lower().strip()
    configured = _configured_providers()
    named = {provider.name: provider for provider in configured}

    if requested in {"auto", ""}:
        return CascadeProvider([*configured, MockProvider()])
    if requested == "groq":
        return named.get("groq") or GroqProvider(settings.groq_api_key, settings.groq_base_url, settings.groq_model)
    if requested == "gemini":
        return named.get("gemini") or GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    if requested == "openrouter":
        return named.get("openrouter") or OpenRouterProvider(
            settings.openrouter_api_key, settings.openrouter_base_url, settings.openrouter_model
        )
    if requested == "pollinations":
        return named["pollinations"]
    if requested == "openai":
        return OpenAICompatibleProvider(
            settings.openai_api_key,
            settings.openai_base_url,
            settings.openai_model,
            use_responses_api=settings.openai_use_responses_api,
            reasoning_effort=settings.openai_reasoning_effort,
        )
    if requested == "ollama":
        return named.get("ollama") or OllamaProvider(
            settings.ollama_base_url,
            settings.ollama_model,
            auto_pull=settings.ollama_auto_pull,
        )
    if requested == "kaggle":
        return KaggleProvider()
    return MockProvider()


def _provider_is_live(provider: LLMProvider) -> bool:
    if isinstance(provider, CascadeProvider):
        return any(_provider_is_live(item) for item in provider.providers if item.name != "mock")
    if provider.name in {"mock", "kaggle"}:
        return False
    if provider.name == "pollinations":
        return True  # anonymous but reachable by default
    if provider.name == "ollama":
        # Don't claim live – Ollama may not be running; cascade will detect at call time
        return False
    return bool(getattr(provider, "api_key", ""))


def llm_status() -> dict:
    settings = get_settings()
    provider = get_provider()
    model = getattr(provider, "model", provider.name)
    live = settings.ai_enabled and _provider_is_live(provider)
    chain = []
    if isinstance(provider, CascadeProvider):
        chain = [item.name for item in provider.providers]
    # Determine best live provider name for hint
    live_provider_name = provider.name
    if isinstance(provider, CascadeProvider) and provider.last_used:
        live_provider_name = provider.last_used.name
    return {
        "ai_enabled": settings.ai_enabled,
        "requested_provider": settings.llm_provider,
        "provider": provider.name,
        "model": model,
        "live": bool(live),
        "human_in_the_loop": True,
        "auto_send": False,
        "auto_draft_enabled": settings.auto_draft_enabled,
        "auto_polish_with_llm": settings.auto_polish_with_llm,
        "chain": chain,
        "hint": (
            "Live drafting active: free LLM cascade tries Groq → Gemini → OpenRouter → Pollinations. "
            "Sending still requires your human verification checklist."
            if live
            else (
                "Template fallback mode: set HJ_GROQ_API_KEY, HJ_GEMINI_API_KEY, or HJ_OPENROUTER_API_KEY "
                "(all free) to enable real LLM drafting. Pollinations (anonymous) is always the last resort."
            )
        ),
    }


class CachedLLM:
    def __init__(self, session: AsyncSession, provider: Optional[LLMProvider] = None):
        self.session = session
        self.provider = provider or get_provider()
        self.prompt_version = "v3"

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
        if cached and not is_fallback_text(cached.response):
            return cached.response
        try:
            response = await self.provider.complete(prompt, system=system)
        except Exception as exc:
            response = f"[LLMError] {exc}. Using template mode."
        if not is_fallback_text(response):
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
