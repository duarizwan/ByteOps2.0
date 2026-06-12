"""Tests for context-aware intent routing and the specialist handoff protocol."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.gmail_agent import GMAIL_SYSTEM_PROMPT
from app.agents.orchestrator import detect_intent_smart, parse_handoff
from app.agents.response_format import HANDOFF_PREFIX
from app.core.llm_client import LLMResponse, TextBlock


def _fake_llm(label: str) -> MagicMock:
    llm = MagicMock()
    llm.create_message = AsyncMock(
        return_value=LLMResponse(content=[TextBlock(text=label)], stop_reason="end_turn")
    )
    return llm


# ── parse_handoff ──────────────────────────────────────────────────────────────

def test_parse_handoff_returns_target_for_sentinel():
    assert parse_handoff("HANDOFF:slack") == "slack"
    assert parse_handoff("  HANDOFF: Slack ") == "slack"
    assert parse_handoff("handoff:jira") == "jira"


def test_parse_handoff_maps_unknown_target_to_general():
    assert parse_handoff("HANDOFF:trello") == "general"
    assert parse_handoff("HANDOFF:") == "general"


def test_parse_handoff_returns_none_for_normal_text():
    assert parse_handoff("Here are your unread emails.") is None
    assert parse_handoff("") is None
    assert parse_handoff(None) is None


# ── detect_intent_smart ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_explicit_service_name_routes_without_llm():
    llm = _fake_llm("general")
    with patch("app.agents.orchestrator.get_llm_client", return_value=llm):
        assert await detect_intent_smart("post an update in slack") == "slack"
    llm.create_message.assert_not_awaited()


@pytest.mark.anyio
async def test_dominant_keyword_score_routes_without_llm():
    llm = _fake_llm("general")
    with patch("app.agents.orchestrator.get_llm_client", return_value=llm):
        assert await detect_intent_smart("show unread emails in my inbox") == "gmail"
    llm.create_message.assert_not_awaited()


@pytest.mark.anyio
async def test_ambiguous_message_is_classified_by_llm():
    # "reply to the thread" scores gmail=2, slack=1 — ambiguous, so the LLM
    # (which sees the conversation context) makes the call.
    llm = _fake_llm("slack")
    history = [
        {"role": "user", "content": "show me the #general channel"},
        {"role": "assistant", "content": "Here are the latest messages in #general..."},
    ]
    with patch("app.agents.orchestrator.get_llm_client", return_value=llm):
        intent = await detect_intent_smart("reply to the thread from John", history)
    assert intent == "slack"
    llm.create_message.assert_awaited_once()


@pytest.mark.anyio
async def test_llm_failure_falls_back_to_keyword_router():
    llm = MagicMock()
    llm.create_message = AsyncMock(side_effect=RuntimeError("provider down"))
    with patch("app.agents.orchestrator.get_llm_client", return_value=llm):
        intent = await detect_intent_smart("reply to the thread from John", [])
    assert intent == "gmail"  # keyword fallback: gmail=2 beats slack=1


# ── specialist prompts ─────────────────────────────────────────────────────────

def test_gmail_prompt_no_longer_hard_refuses():
    assert "I only handle Gmail" not in GMAIL_SYSTEM_PROMPT
    assert "the routing system will get you to the right tool" not in GMAIL_SYSTEM_PROMPT


def test_gmail_prompt_includes_handoff_protocol():
    assert HANDOFF_PREFIX in GMAIL_SYSTEM_PROMPT
