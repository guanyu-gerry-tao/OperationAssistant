import os
import re
from dataclasses import asdict, dataclass
from time import perf_counter, sleep
from typing import Literal

import httpx


ChatRole = Literal["system", "user", "assistant"]


class LLMProviderConfigurationError(RuntimeError):
    """Raised when a real provider is requested without a configured secret boundary."""


@dataclass(frozen=True)
class ChatMessage:
    """One chat message passed to a provider adapter."""

    role: ChatRole
    content: str

    def to_dict(self) -> dict[str, str]:
        """Return the SDK-shaped message payload."""

        return asdict(self)


@dataclass(frozen=True)
class LLMUsage:
    """Token accounting returned by a provider call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict[str, int]:
        """Return a JSON-friendly usage payload."""

        return asdict(self)


@dataclass(frozen=True)
class LLMResponse:
    """Provider response with only report-safe metadata."""

    provider: str
    model: str
    content: str
    usage: LLMUsage
    latency_ms: float

    def to_safe_dict(self) -> dict[str, object]:
        """Return report-safe fields that never include API keys."""

        return {
            "provider": self.provider,
            "model": self.model,
            "content": self.content,
            "usage": self.usage.to_dict(),
            "latency_ms": self.latency_ms,
        }


class DeterministicLLMProvider:
    """Deterministic provider used only for dry-run and CI sanity checks."""

    provider_name = "deterministic"

    def is_configured(self) -> bool:
        """Return whether the provider can run without external secrets."""

        return True

    def safe_config_summary(self) -> dict[str, object]:
        """Return report-safe deterministic provider metadata."""

        return {
            "provider": self.provider_name,
            "configured": True,
            "secret_boundary": "none",
        }

    def complete(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        temperature: float,
        timeout_seconds: float,
    ) -> LLMResponse:
        """Return a deterministic answer derived from the provided prompt context."""

        del temperature, timeout_seconds
        started_at = perf_counter()
        content = self._build_content(messages)
        prompt_tokens = sum(_estimate_tokens(message.content) for message in messages)
        completion_tokens = _estimate_tokens(content)
        return LLMResponse(
            provider=self.provider_name,
            model=model,
            content=content,
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            latency_ms=round((perf_counter() - started_at) * 1000, 3),
        )

    def _build_content(self, messages: list[ChatMessage]) -> str:
        """Build deterministic dry-run text without using hidden eval labels."""

        prompt = messages[-1].content if messages else ""
        if "Return JSON" in prompt and "tool_calls" in prompt:
            return self._build_tool_plan(prompt)

        source_ids = sorted(set(re.findall(r"\bRB-\d+\b", prompt)))
        high_signal_terms = _extract_high_signal_terms(prompt)
        evidence_parts: list[str] = []
        if source_ids:
            evidence_parts.append("Citations: " + ", ".join(source_ids) + ".")
        if high_signal_terms:
            evidence_parts.append("Evidence terms: " + ", ".join(high_signal_terms[:10]) + ".")
        if "Tool outputs:" in prompt:
            evidence_parts.append("Read-only tool evidence was included.")
        if not evidence_parts:
            evidence_parts.append("No retrieved citations or tool outputs were supplied.")

        return (
            "Deterministic dry-run answer. "
            + " ".join(evidence_parts)
            + " Recommended next step: continue evidence gathering before any write action."
        )

    def _build_tool_plan(self, prompt: str) -> str:
        """Return a deterministic function-calling style tool plan."""

        incident_match = re.search(r"Incident id:\s*(INC-\d+)", prompt)
        incident_id = incident_match.group(1) if incident_match else "INC-1001"
        searchable = prompt.lower()
        calls = [
            {
                "tool_name": "get_incident_summary",
                "arguments": {"incident_id": incident_id},
                "reason": "Ground the incident context first.",
            }
        ]
        if any(term in searchable for term in ["workflow", "retry", "payment", "checkout"]):
            calls.append(
                {
                    "tool_name": "get_failed_events",
                    "arguments": {"incident_id": incident_id},
                    "reason": "Failed event evidence is relevant.",
                }
            )
        elif any(term in searchable for term in ["metric", "error rate", "inventory", "feed", "validation"]):
            calls.append(
                {
                    "tool_name": "get_service_metrics",
                    "arguments": {"incident_id": incident_id},
                    "reason": "Metric evidence is relevant.",
                }
            )
        elif any(term in searchable for term in ["latency", "queue", "worker", "notification"]):
            calls.append(
                {
                    "tool_name": "get_trace_like_records",
                    "arguments": {"incident_id": incident_id},
                    "reason": "Trace-like evidence is relevant.",
                }
            )
        return '{"tool_calls": ' + repr(calls).replace("'", '"') + "}"


class OpenAICompatibleProvider:
    """HTTP adapter for OpenAI-compatible chat completion providers."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key_env: str = "OPENAI_API_KEY",
        base_url_env: str = "OPENAI_BASE_URL",
        default_base_url: str = "https://api.openai.com/v1",
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        """Create a provider adapter that reads keys only from environment variables."""

        self.api_key_env = api_key_env
        self.base_url_env = base_url_env
        self.default_base_url = default_base_url.rstrip("/")
        self.transport = transport
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def is_configured(self) -> bool:
        """Return whether the API key environment variable is present."""

        return bool(os.environ.get(self.api_key_env))

    def safe_config_summary(self) -> dict[str, object]:
        """Return report-safe provider metadata without secret values."""

        return {
            "provider": self.provider_name,
            "api_key_env": self.api_key_env,
            "base_url": self._base_url(),
            "configured": self.is_configured(),
        }

    def complete(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        temperature: float,
        timeout_seconds: float,
    ) -> LLMResponse:
        """Call the provider chat completion endpoint and parse the text response."""

        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise LLMProviderConfigurationError(
                f"{self.api_key_env} is not set; refusing to run a real LLM eval."
            )

        started_at = perf_counter()
        payload = {
            "model": model,
            "messages": [message.to_dict() for message in messages],
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        response_payload = self._post_with_retries(
            headers=headers,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )

        choice = response_payload["choices"][0]
        content = str(choice.get("message", {}).get("content", ""))
        usage_payload = response_payload.get("usage", {})
        usage = LLMUsage(
            prompt_tokens=int(usage_payload.get("prompt_tokens", 0)),
            completion_tokens=int(usage_payload.get("completion_tokens", 0)),
            total_tokens=int(usage_payload.get("total_tokens", 0)),
        )
        return LLMResponse(
            provider=self.provider_name,
            model=model,
            content=content,
            usage=usage,
            latency_ms=round((perf_counter() - started_at) * 1000, 3),
        )

    def _base_url(self) -> str:
        """Return the configured base URL without trailing slash."""

        return os.environ.get(self.base_url_env, self.default_base_url).rstrip("/")

    def _post_with_retries(
        self,
        *,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        """Post one chat completion request, retrying transient transport failures."""

        attempts = self.max_retries + 1
        last_error: Exception | None = None
        for attempt_index in range(attempts):
            client_kwargs: dict[str, object] = {"timeout": timeout_seconds}
            if self.transport is not None:
                client_kwargs["transport"] = self.transport
            try:
                with httpx.Client(**client_kwargs) as client:
                    response = client.post(f"{self._base_url()}/chat/completions", headers=headers, json=payload)
                    response.raise_for_status()
                    parsed = response.json()
                    if isinstance(parsed, dict):
                        return parsed
                    raise RuntimeError("Provider returned a non-object JSON payload")
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt_index >= self.max_retries:
                    raise
                if self.retry_backoff_seconds > 0:
                    sleep(self.retry_backoff_seconds)

        raise RuntimeError("Provider request failed") from last_error


def estimate_cost_usd(
    usage: LLMUsage,
    *,
    input_cost_per_1m: float,
    output_cost_per_1m: float,
) -> float:
    """Estimate provider cost from explicit per-million token prices."""

    input_cost = (usage.prompt_tokens / 1_000_000) * input_cost_per_1m
    output_cost = (usage.completion_tokens / 1_000_000) * output_cost_per_1m
    return round(input_cost + output_cost, 6)


def _estimate_tokens(text: str) -> int:
    """Return a lightweight token estimate for deterministic dry-run accounting."""

    return max(len(text.split()), 1)


def _extract_high_signal_terms(prompt: str) -> list[str]:
    """Extract sample evidence terms that the deterministic dry-run answer should expose."""

    patterns = [
        r"\bINC-\d+\b",
        r"\bwf-[A-Za-z0-9-]+\b",
        r"Payment authorization timeout",
        r"retry budget",
        r"checkout-workflow",
        r"inventory-sync",
        r"partner feed validation",
        r"validation_error_rate",
        r"notification-worker",
        r"queue",
        r"latency",
        r"write action",
    ]
    terms: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, prompt, flags=re.IGNORECASE):
            value = str(match)
            if value not in terms:
                terms.append(value)
    return terms
