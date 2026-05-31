"""Provider-agnostic async LLM client.

Supported providers (first key present in .env wins):
  CLAUDE_API_KEY → Anthropic  (anthropic SDK)
  GEMINI_API_KEY → Google Gemini (OpenAI-compatible endpoint)
  GROQ_API_KEY   → Groq         (OpenAI-compatible endpoint)

Default models:
  Claude  → claude-sonnet-4-6
  Gemini  → gemini-2.0-flash
  Groq    → llama-3.3-70b-versatile

Override with LLM_MODEL in .env.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, AsyncIterator


class RateLimitError(Exception):
    """Raised when the active LLM provider returns a rate-limit response."""


@dataclass
class TextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class ToolUseBlock:
    type: str = "tool_use"
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    content: list[TextBlock | ToolUseBlock]
    stop_reason: str
    # Provider-native assistant message dict — used by append_response()
    _native: dict = field(default_factory=dict, repr=False)


class LLMClient:
    """Auto-detecting async LLM client. Wraps Anthropic, Gemini (OAI-compat), Groq (OAI-compat)."""

    def __init__(self) -> None:
        from app.core.config import get_settings
        settings = get_settings()

        if settings.claude_api_key:
            import anthropic as _ant
            self._provider = "anthropic"
            self._client = _ant.AsyncAnthropic(api_key=settings.claude_api_key)
            self._ant = _ant
            self.default_model = settings.llm_model or "claude-sonnet-4-6"

        elif settings.gemini_api_key:
            from openai import AsyncOpenAI
            self._provider = "gemini"
            self._client = AsyncOpenAI(
                api_key=settings.gemini_api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
            self._ant = None
            self.default_model = settings.llm_model or "gemini-2.0-flash"

        elif settings.groq_api_key:
            from openai import AsyncOpenAI
            self._provider = "groq"
            self._client = AsyncOpenAI(
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )
            self._ant = None
            self.default_model = settings.llm_model or "llama-3.3-70b-versatile"

        else:
            raise ValueError(
                "No LLM API key found. Set CLAUDE_API_KEY, GEMINI_API_KEY, "
                "or GROQ_API_KEY in your .env file."
            )

    # ── Public interface ───────────────────────────────────────────────────────

    async def create_message(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 8192,
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """Non-streaming call. tools must use Anthropic schema (input_schema key)."""
        model = model or self.default_model
        try:
            if self._provider == "anthropic":
                return await self._ant_create(messages, system, max_tokens, tools, model)
            return await self._oai_create(messages, system, max_tokens, tools, model)
        except Exception as exc:
            if self._is_rate_limit(exc):
                raise RateLimitError(str(exc)) from exc
            raise

    async def stream_text(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 8192,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """Streaming text. Yields string deltas."""
        model = model or self.default_model
        try:
            if self._provider == "anthropic":
                async for chunk in self._ant_stream(messages, system, max_tokens, model):
                    yield chunk
            else:
                async for chunk in self._oai_stream(messages, system, max_tokens, model):
                    yield chunk
        except Exception as exc:
            if self._is_rate_limit(exc):
                raise RateLimitError(str(exc)) from exc
            raise

    def append_response(self, messages: list[dict], response: LLMResponse) -> None:
        """Append the assistant turn to messages in provider-native format."""
        messages.append(response._native)

    def append_tool_results(
        self, messages: list[dict], results: list[dict]
    ) -> None:
        """Append tool results.  results = [{"tool_use_id": str, "content": str}]"""
        if self._provider == "anthropic":
            messages.append({
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": r["tool_use_id"], "content": r["content"]}
                    for r in results
                ],
            })
        else:
            for r in results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": r["tool_use_id"],
                    "content": r["content"],
                })

    # ── Anthropic backend ──────────────────────────────────────────────────────

    async def _ant_create(
        self, messages, system, max_tokens, tools, model
    ) -> LLMResponse:
        kwargs: dict[str, Any] = dict(model=model, max_tokens=max_tokens, messages=messages)
        if system:
            kwargs["system"] = system
        kwargs["tools"] = tools if tools else self._ant.NOT_GIVEN

        resp = await self._client.messages.create(**kwargs)

        content: list[TextBlock | ToolUseBlock] = []
        for b in resp.content:
            if b.type == "text":
                content.append(TextBlock(text=b.text))
            elif b.type == "tool_use":
                content.append(ToolUseBlock(id=b.id, name=b.name, input=b.input))

        return LLMResponse(
            content=content,
            stop_reason=resp.stop_reason or "end_turn",
            _native={"role": "assistant", "content": resp.content},
        )

    async def _ant_stream(
        self, messages, system, max_tokens, model
    ) -> AsyncIterator[str]:
        kwargs: dict[str, Any] = dict(model=model, max_tokens=max_tokens, messages=messages)
        if system:
            kwargs["system"] = system
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    # ── OpenAI-compatible backend (Gemini / Groq) ─────────────────────────────

    def _oai_messages(self, messages: list[dict], system: str) -> list[dict]:
        """Normalise message history for OpenAI-compatible endpoints."""
        result: list[dict] = []
        if system:
            result.append({"role": "system", "content": system})

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content")

            # Already-native OpenAI messages (appended by this client in prior turns)
            if role == "tool" or (role == "assistant" and "tool_calls" in msg):
                result.append(msg)
                continue

            if isinstance(content, str) or content is None:
                result.append({"role": role, "content": content or ""})
            elif isinstance(content, list):
                # Anthropic-style content blocks (history edge case)
                text = " ".join(
                    (b.text if hasattr(b, "text") else b.get("text", ""))
                    for b in content
                    if (hasattr(b, "type") and getattr(b, "type") == "text")
                    or (isinstance(b, dict) and b.get("type") == "text")
                )
                result.append({"role": role, "content": text})

        return result

    def _oai_tools(self, tools: list[dict]) -> list[dict]:
        """Convert Anthropic tool schema (input_schema) → OpenAI (parameters)."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            }
            for t in tools
        ]

    async def _oai_create(
        self, messages, system, max_tokens, tools, model
    ) -> LLMResponse:
        kwargs: dict[str, Any] = dict(
            model=model,
            max_tokens=max_tokens,
            messages=self._oai_messages(messages, system),
        )
        if tools:
            kwargs["tools"] = self._oai_tools(tools)
            kwargs["tool_choice"] = "auto"

        resp = await self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        content: list[TextBlock | ToolUseBlock] = []
        if msg.content:
            content.append(TextBlock(text=msg.content))
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    inp = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    inp = {}
                content.append(ToolUseBlock(id=tc.id, name=tc.function.name, input=inp))

        native: dict[str, Any] = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            native["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]

        return LLMResponse(
            content=content,
            stop_reason="tool_use" if msg.tool_calls else "end_turn",
            _native=native,
        )

    async def _oai_stream(
        self, messages, system, max_tokens, model
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=self._oai_messages(messages, system),
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _is_rate_limit(self, exc: Exception) -> bool:
        return "RateLimit" in type(exc).__name__ or "rate_limit" in str(exc).lower()


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Cached singleton LLMClient — re-detected on server restart."""
    return LLMClient()
