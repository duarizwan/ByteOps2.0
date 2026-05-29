"""Tests for the shared RESPONSE_FORMAT constant."""
from app.agents.response_format import RESPONSE_FORMAT
from app.agents.orchestrator import build_system_prompt
from app.agents.gmail_agent import GMAIL_SYSTEM_PROMPT
from app.agents.calendar_agent import CALENDAR_SYSTEM_PROMPT
from app.agents.github_agent import GITHUB_SYSTEM_PROMPT
from app.agents.slack_agent import SLACK_SYSTEM_PROMPT
from app.agents.jira_agent import JIRA_SYSTEM_PROMPT
from app.agents.dropbox_agent import DROPBOX_SYSTEM_PROMPT


def test_response_format_bans_headers():
    assert "No headers" in RESPONSE_FORMAT


def test_response_format_bans_bold():
    assert "No bold" in RESPONSE_FORMAT


def test_response_format_bans_dividers():
    assert "No horizontal rules" in RESPONSE_FORMAT


def test_response_format_allows_tables_for_structured_data():
    assert "plain table is allowed" in RESPONSE_FORMAT


def test_response_format_is_string():
    assert isinstance(RESPONSE_FORMAT, str)
    assert len(RESPONSE_FORMAT) > 50


def test_orchestrator_prompt_contains_format_rules():
    prompt = build_system_prompt([])
    assert "No headers" in prompt
    assert "plain, natural prose" in prompt


def test_orchestrator_prompt_no_legacy_markdown_instruction():
    prompt = build_system_prompt([])
    assert "Use Markdown for structured answers" not in prompt


def test_gmail_prompt_contains_format_rules():
    assert "No headers" in GMAIL_SYSTEM_PROMPT
    assert "Format all responses in clean Markdown" not in GMAIL_SYSTEM_PROMPT


def test_calendar_prompt_contains_format_rules():
    assert "No headers" in CALENDAR_SYSTEM_PROMPT
    assert "Format all responses in clean Markdown" not in CALENDAR_SYSTEM_PROMPT


def test_github_prompt_contains_format_rules():
    assert "No headers" in GITHUB_SYSTEM_PROMPT
    assert "Format all responses in clean Markdown" not in GITHUB_SYSTEM_PROMPT


def test_slack_prompt_contains_format_rules():
    assert "No headers" in SLACK_SYSTEM_PROMPT
    assert "Format all responses in clean Markdown" not in SLACK_SYSTEM_PROMPT


def test_jira_prompt_contains_format_rules():
    assert "No headers" in JIRA_SYSTEM_PROMPT
    assert "plain table is allowed" in JIRA_SYSTEM_PROMPT
    assert "Format responses in clean Markdown tables" not in JIRA_SYSTEM_PROMPT


def test_dropbox_prompt_contains_format_rules():
    assert "No headers" in DROPBOX_SYSTEM_PROMPT
    assert "plain table is allowed" in DROPBOX_SYSTEM_PROMPT
    assert "Format file listings as clean Markdown tables" not in DROPBOX_SYSTEM_PROMPT


def test_response_format_mentions_help_icon():
    assert "? Help button" in RESPONSE_FORMAT
