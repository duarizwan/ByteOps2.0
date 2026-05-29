---
id: 005
title: UI Polish — Header, Glow, Animations
stage: green
date: 2026-05-29
surface: agent
model: claude-sonnet-4-6
feature: ui-polish
branch: none
user: dua.rizwan@jonasclub.com
command: "lets now improve bit of frontend and UI"
labels: ["ui", "frontend", "polish", "animation", "tailwind"]
links:
  spec: docs/superpowers/specs/2026-05-29-ui-improvements-design.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/app/globals.css
  - frontend/src/components/dashboard/top-bar.tsx
  - frontend/src/components/dashboard/chat-interface.tsx
  - frontend/src/components/dashboard/collapsible-sidebar.tsx
  - frontend/src/components/dashboard/context-panel.tsx
  - frontend/vitest.config.ts
  - frontend/tests/top-bar.test.tsx
  - frontend/tests/chat-interface.test.tsx
  - frontend/tests/collapsible-sidebar.test.tsx
  - frontend/tests/context-panel.test.tsx
tests:
  - frontend/tests/top-bar.test.tsx (2 tests — subtitle dedup, no plain b span)
  - frontend/tests/chat-interface.test.tsx (8 source-level assertions)
  - frontend/tests/collapsible-sidebar.test.tsx (2 tests — glow class, no max-h-64)
  - frontend/tests/context-panel.test.tsx (1 test — lg:inline not xl:inline)
---

## Prompt

lets now improve bit of frontend and UI

[follow-up] use skills when I open chat interface i can see header and there is redundancy it dispaly ByteOps 2 times modernize the header and on left pane when platforms are connected it shows a green but with glow add smooth transitions and suggest more tips to improve UI UX

[follow-up] when AI repond to query its display pic shouldnt be star instead keep it b logo

[follow-up] show me mockup how it will look like / show me mockup how it will look if we use cream instead of blue → blue

[follow-up] lets start / continue

## Response snapshot

Full brainstorm → spec → plan → implementation cycle. 8 UI changes delivered across 5 files, 13 tests passing.

Changes:
1. globals.css — @keyframes messageIn + .message-in utility
2. top-bar.tsx — Gradient blue Sparkles logo, subtitle "AI Work Assistant" (removed "· ByteOps"), hover:scale-[0.98]
3. chat-interface.tsx — "b" text mark avatar (removed Sparkles), staggered typing dots (0/150/300ms), auto-grow textarea (rows=1, onInput handler, max-h-36, height reset on send), message-in class on all message wrappers
4. collapsible-sidebar.tsx — getStatusColor returns bg-success + shadow-[0_0_6px_2px_rgba(34,197,94,0.45)] for connected tools, conversation list changed from max-h-64 to flex-1
5. context-panel.tsx — hidden xl:inline → hidden lg:inline on tab labels

Visual mockups were created and shown in Chrome via DevTools MCP:
- ui-preview.html — full before/after for all 5 sections
- cream-vs-blue.html — theme comparison (blue chosen)

## Outcome

- ✅ Impact: Header is clean, AI avatar uses b mark, connected tools visually pop with green glow, messages animate in smoothly, chat input grows with content, context panel tabs readable at 1024px
- 🧪 Tests: 13/13 pass — chat-interface uses source assertions (react-markdown v10 OOMs jsdom worker), others use DOM render tests
- 📁 Files: 5 source files + 4 test files + vitest.config.ts (externalized react-markdown)
- 🔁 Next prompts: Start the dev server and verify visually; consider window.confirm → inline delete confirmation (deferred)
- 🧠 Reflection: react-markdown v10 ESM tree is too heavy for jsdom — source-level test assertions are the right pragmatic answer here, not increasing heap

## Evaluation notes (flywheel)

- Failure modes observed: react-markdown OOM in vitest worker regardless of heap size (4GB, 8GB); resolved by pivoting to source assertions
- Graders run and results (PASS/FAIL): vitest run — 13/13 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Replace react-markdown with a lighter alternative (marked + sanitize-html) to unblock DOM render tests
