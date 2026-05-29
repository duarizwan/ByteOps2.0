---
id: 001
title: Add Help Popover to Chat Header
stage: green
date: 2026-05-29
surface: agent
model: claude-sonnet-4-6
feature: help-center
branch: master
user: dua.rizwan@jonasclub.com
command: P2-T2 implement help popover
labels: ["help-center","popover","chat-interface","frontend","react","typescript"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/components/dashboard/chat-interface.tsx
  - frontend/tests/chat-interface.test.tsx
tests:
  - tests/chat-interface.test.tsx (16 tests, 15 pass, 1 pre-existing fail)
---

## Prompt

Implement Task 2 of the ByteOps help-center feature: add a help (?) popover to the chat header in `frontend/src/components/dashboard/chat-interface.tsx`. The popover uses plain React state (no Radix UI / shadcn), imports `useToolConnections` hook and `TOOL_CAPABILITIES` lib, shows connected tools and their capabilities, and closes on click-outside. Add 8 new source-level tests, confirm they fail first, then implement, confirm all 8 pass, and commit.

## Response snapshot

All 8 new tests written and confirmed failing before implementation. Then applied 5 targeted edits to chat-interface.tsx:
1. Added `HelpCircle` to lucide-react import
2. Added `useToolConnections` and `TOOL_CAPABILITIES` imports after `ByteOpsLogoMark`
3. Added `showHelp`/`setShowHelp` state, `helpRef`, `connections`, and `connectedTools` declarations
4. Added click-outside `useEffect` with `handleClickOutside` and `removeEventListener` cleanup
5. Replaced flat chat header div with flex layout containing the help button + conditional popover rendering

Full suite result: 15/16 tests pass. The 1 failure ("AI avatar renders the b mark") is pre-existing from a prior task and unrelated to Task 2.

Commit: ca4a854

## Outcome

- Impact: Help popover added to chat header; users can see per-tool capabilities for all connected tools
- Tests: 15/16 pass; 8 new Task-2 tests all pass; 1 pre-existing unrelated failure
- Files: 2 files modified (chat-interface.tsx + test file)
- Next prompts: P2-T3 — add help icon mention to RESPONSE_FORMAT
- Reflection: Source-level test pattern (readFileSync) is effective for large ESM-only components; click-outside cleanup pattern correctly uses conditional addEventListener in useEffect

## Evaluation notes (flywheel)

- Failure modes observed: none for Task 2; pre-existing "b mark" test failure is from Task 1 mismatch
- Graders run and results (PASS/FAIL): vitest run — 15 PASS / 1 pre-existing FAIL
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): fix pre-existing "b mark" test if owner wants clean suite
