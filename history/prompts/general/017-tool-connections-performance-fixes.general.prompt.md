---
id: "017"
title: Tool connections performance fixes
stage: green
date: 2026-06-11
surface: agent
model: claude-4.6-sonnet-medium-thinking
feature: none
branch: unknown
user: rizwadua
command: null
labels: ["performance", "tool-connections", "provider", "auth-cache"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - frontend/src/providers/tool-connections-provider.tsx
 - frontend/src/components/app-providers.tsx
 - frontend/src/hooks/use-tool-connections.ts
 - frontend/src/app/layout.tsx
 - frontend/src/app/settings/page.tsx
 - frontend/src/components/dashboard/tool-card.tsx
 - backend/app/core/auth.py
 - frontend/tests/tool-connections.test.tsx
tests:
 - frontend/tests/tool-connections.test.tsx
 - backend/tests/test_oauth.py
---

## Prompt

do the recommended one

## Response snapshot

Implemented three performance fixes: ToolConnectionsProvider (single shared fetch + in-flight dedup), optimistic settings UI (tool cards render immediately with Checking badge), and backend auth user snapshot cache (skips DB round-trip on cache hit).

## Outcome

- ✅ Impact: Settings/tools page should load ~2-3x faster with one API call instead of three
- 🧪 Tests: frontend tool-connections tests pass
- 📁 Files: provider, layout, settings, tool-card, auth.py
- 🔁 Next prompts: Verify in Network tab; set DEBUG=false for extra backend speed
- 🧠 Reflection: Context provider is zero-dependency alternative to SWR

## Evaluation notes (flywheel)

- Failure modes observed: n/a
- Graders run and results (PASS/FAIL): frontend PASS
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
