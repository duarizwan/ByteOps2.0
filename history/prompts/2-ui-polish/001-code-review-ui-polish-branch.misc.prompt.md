---
id: "001"
title: "Code Review UI Polish Branch"
stage: misc
date: "2026-05-31"
surface: agent
model: claude-sonnet-4-6
feature: 2-ui-polish
branch: 1-agent-runs-graph
user: Dua Rizwan
command: /sp.phr
labels: ["code-review", "ui-polish", "action-center", "bug-findings", "test-fix"]
links:
  spec: "specs/2-ui-polish/spec.md"
  ticket: "null"
  adr: "null"
  pr: "null"
files:
  - frontend/src/lib/classify-error.ts
tests:
  - frontend/tests/classify-error.test.ts
---

## Prompt

summary of last task

## Response

Ran a full 7-angle code review (line-by-line, removed-behavior, cross-file, reuse, simplification, efficiency, altitude) against the `1-agent-runs-graph` branch (base: `main`, 7 files, 1644 insertions). Found and verified 10 findings — 4 CONFIRMED bugs, 3 PLAUSIBLE issues, 3 cleanup items. Also fixed a failing test (`classifyError` missing `"api error"` in `TIMEOUT_RE`). All 182 tests now pass. Branch is ready for finishing.

## Outcome / Impact

- 4 CONFIRMED bugs identified before merge:
  1. Premature `setIsTyping(false)` on `workflow_draft` — concurrent stream race / message corruption
  2. Runs with `status='running'` invisible in Action Center
  3. `handleApprove`/`handleReject` unhandled errors, no UI feedback
  4. Failed runs permanently pinned (no dismiss path)
- Test suite fixed: `classify-error.test.ts` was failing due to missing `"api error"` pattern
- All 182 tests passing; branch is in a mergeable state pending bug fixes

## Tests Summary

- `frontend/tests/classify-error.test.ts` — 1 failure fixed, now passing (182 total pass, 3 skipped)

## Files Modified

- `frontend/src/lib/classify-error.ts` — added `api error` to `TIMEOUT_RE`

## Next Steps

- Fix the 4 confirmed bugs before merging (especially concurrent stream race and running-run invisibility)
- Choose merge/PR option via `superpowers:finishing-a-development-branch`

## Reflection

The most impactful finding was the premature `setIsTyping(false)` on `workflow_draft` — it's subtle (workflow_draft is a valid mid-stream event) but causes real data corruption when users type during a long-running agent stream.

---

**Failure modes observed:** No PHR template or history directory existed; had to create both from scratch. Labels assigned manually without script validation.

**Next experiment:** Add `.specify/templates/phr-template.prompt.md` and `history/prompts/` baseline structure to the repo so future PHR creation uses the standard script flow.
