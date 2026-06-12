---
id: "011"
title: Vary Loading Stage Messages
stage: general
date: 2026-06-02
surface: agent
model: claude-sonnet-4-6
feature: none
branch: 1-agent-runs-graph
user: Dua Rizwan
command: chat
labels: ["ux","loading-state","chat-interface","perceived-performance"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/components/dashboard/chat-interface.tsx
tests:
  - frontend/tests/chat-interface.test.tsx (existing, unchanged)
---

## Prompt

is it possible to increase the speed of while tool calling and AI responding and do not always say "understanding req ..." keep changing it so that user stay engaged and patient

## Response snapshot

Answered the speed question (inference speed is model-provider-controlled; streaming + keepalives already in place). Implemented rotating stage labels with a fade crossfade animation.

Changes made to `frontend/src/components/dashboard/chat-interface.tsx`:
- Changed `STAGE_LABELS` from `{key: string}` to `{key: string[]}` with 4–6 variations per stage (understanding, routing, awaiting, finalizing).
- Added `CyclingStageLabel` component: cycles messages every 2.8 s with a 200 ms opacity fade-out/in transition.
- Stage keys stored as plain strings ("understanding", "routing", "awaiting") in `message.stage` instead of the full label text.
- Render updated to use `<CyclingStageLabel stageKey={message.stage} />`.

## Outcome

- ✅ Impact: Loading states now rotate through natural-language variants, reducing perceived wait time and keeping users engaged.
- 🧪 Tests: Existing source-level test still passes (no assertion on exact label text).
- 📁 Files: 1 file modified.
- 🔁 Next prompts: Could add per-tool-name routing messages ("Checking GitHub…", "Scanning Gmail…") once tool name is surfaced in the stage.
- 🧠 Reflection: Minimal change; no model speed improvement possible from the frontend, but cycling text + existing streaming already gives best perceived performance.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): n/a
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): Pass tool name from `tool_call_start` event into stage key so routing messages can say "Checking GitHub…" instead of generic text.
