from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.core.llm_client import LLMClient


def test_settings_treats_release_debug_env_as_false(monkeypatch):
    monkeypatch.setenv("DEBUG", "release")

    settings = Settings(_env_file=None)

    assert settings.debug is False


def test_llm_client_uses_explicit_claude_provider_with_claude_default():
    settings = MagicMock(
        llm_provider="claude",
        claude_api_key="test-claude-key",
        gemini_api_key="test-gemini-key",
        groq_api_key="",
        llm_model="",
    )

    with patch("app.core.config.get_settings", return_value=settings):
        client = LLMClient()

    assert client._provider == "anthropic"
    assert client.default_model == "claude-sonnet-4-6"


def test_llm_client_uses_explicit_gemini_provider_with_gemini_default():
    settings = MagicMock(
        llm_provider="gemini",
        claude_api_key="test-claude-key",
        gemini_api_key="test-gemini-key",
        groq_api_key="",
        llm_model="",
    )

    with patch("app.core.config.get_settings", return_value=settings):
        client = LLMClient()

    assert client._provider == "gemini"
    assert client.default_model == "gemini-2.0-flash"


def test_llm_client_ignores_model_for_wrong_provider():
    settings = MagicMock(
        llm_provider="claude",
        claude_api_key="test-claude-key",
        gemini_api_key="test-gemini-key",
        groq_api_key="",
        llm_model="gemini-2.5-flash",
    )

    with patch("app.core.config.get_settings", return_value=settings):
        client = LLMClient()

    assert client._provider == "anthropic"
    assert client.default_model == "claude-sonnet-4-6"


def test_llm_client_requires_key_for_explicit_provider():
    settings = MagicMock(
        llm_provider="gemini",
        claude_api_key="test-claude-key",
        gemini_api_key="",
        groq_api_key="",
        llm_model="",
    )

    with patch("app.core.config.get_settings", return_value=settings):
        with pytest.raises(ValueError, match="LLM_PROVIDER=gemini requires GEMINI_API_KEY"):
            LLMClient()
