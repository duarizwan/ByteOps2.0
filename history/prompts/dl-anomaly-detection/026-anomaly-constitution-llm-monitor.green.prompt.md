---
id: 026
title: Anomaly constitution + LLM monitor
stage: green
date: 2026-06-13
surface: agent
model: claude-opus-4-8
feature: dl-anomaly-detection
branch: feat/dl-anomaly-detection
user: dua.rizwan@jonasclub.com
command: TASK 13 (TDD implementation)
labels: ["anomaly", "llm-monitor", "tdd", "security"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - backend/app/anomaly/constitution.py
 - backend/app/anomaly/llm_monitor.py
 - backend/tests/test_llm_monitor.py
tests:
 - backend/tests/test_llm_monitor.py::test_parse_score_extracts_answer
 - backend/tests/test_llm_monitor.py::test_parse_score_clamps_and_defaults
 - backend/tests/test_llm_monitor.py::test_parse_score_case_insensitive_and_spacing
---

## Prompt

You are implementing ONE task in repo ByteOps, branch `feat/dl-anomaly-detection`. Strict TDD. Run tests with `cd backend && .venv/Scripts/python.exe -m pytest <path> -v`.

CONTEXT: ByteOps is adding an LLM "black-box monitor" that scores an agent run's observable actions for anomalous/scheming behavior on a 1-10 scale (method from Storf et al. 2026). It reuses the existing async LLM client `app.core.llm_client.get_llm_client()`, which returns a client with `async def create_message(self, messages: list[dict], system: str = "", max_tokens: int = 8192, ...) -> LLMResponse`. `LLMResponse.content` is a list of blocks; text blocks have `.type == "text"` and `.text`. The monitor is action-only (serialize tool calls + outcomes, never chain-of-thought), best-effort (never raises into a run).

=== TASK 13: Anomaly constitution + LLM monitor ===

Step 1 — Create the failing test `backend/tests/test_llm_monitor.py` (parse_score tests).
Step 2 — Run pytest → FAIL (no module).
Step 3 — Create `backend/app/anomaly/constitution.py` (CONSTITUTION_PROMPT) and `backend/app/anomaly/llm_monitor.py` (parse_score, _serialize, async score_run_llm).
Step 4 — Run pytest → all PASS.
Step 5 — Confirm no import errors at module load (score_run_llm must NOT import the llm client at module top).
Step 6 — Commit ONLY the three files.
Do NOT wire it into run completion or add DB columns (next task).

## Response snapshot

Followed strict TDD:
- Wrote `test_llm_monitor.py` first; confirmed it failed with `ModuleNotFoundError: No module named 'app.anomaly.llm_monitor'`.
- Created `constitution.py` with `CONSTITUTION_PROMPT` and `llm_monitor.py` with `parse_score` (regex `ANSWER:\s*(\d+)`, default 5, clamp 1..10), `_serialize`, and best-effort `async score_run_llm` (imports the llm client lazily inside the function, returns None on any exception).
- pytest: 3 passed.
- Import check `python -c "import app.anomaly.llm_monitor; import app.anomaly.constitution; print('ok')"` → `ok` (no API key needed at module load).
- Committed only the three files (SHA 77bc787). CRLF warnings only.

## Outcome

- ✅ Impact: LLM black-box anomaly monitor + constitution available; not yet wired into run completion.
- 🧪 Tests: 3 passed (parse_score extract / clamp+default / case-insensitive).
- 📁 Files: 2 new modules + 1 test file.
- 🔁 Next prompts: wire score_run_llm into run completion and add DB columns (next task).
- 🧠 Reflection: lazy import keeps module load API-key-free as required.

## Evaluation notes (flywheel)

- Failure modes observed: none.
- Graders run and results (PASS/FAIL): pytest PASS (3/3); import-check PASS.
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): integration test for score_run_llm with a mocked llm client.
