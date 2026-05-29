---
id: 003
title: Fix Navigation Sign-in Click Glitches
stage: general
date: 2026-05-28
surface: agent
model: claude-sonnet-4-6
feature: none
branch: none
user: dua.rizwan@jonasclub.com
command: natural language bug report
labels: ["frontend","navigation","clerk","ui","settings","sign-in"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/app/settings/page.tsx
  - frontend/src/app/(auth)/sign-in/[[...sign-in]]/page.tsx
  - frontend/src/components/dashboard/top-bar.tsx
tests:
  - manual: click New Chat on /settings → should navigate to /dashboard
  - manual: sign in → should land on /dashboard not welcome screen
  - manual: click ByteOps logo in TopBar → should navigate to /dashboard
---

## Prompt

when i was on /settings page + new chat btn isnt working it should be work like when i am on settings page on clicking new chat it shows me new chat alsi even afer signing in whenever i am running my project it is showing me welcome screen and i dont know there are some clicking glitches

## Response snapshot

Found 3 root causes via systematic debugging:

1. `settings/page.tsx` onNewChat was `() => {}` (no-op). Added `useRouter` and changed to `router.push("/dashboard")`.

2. `sign-in/page.tsx` used `afterSignInUrl="/dashboard"` which is REMOVED in Clerk v6 (project uses @clerk/nextjs ^6.38.2). Changed to `fallbackRedirectUrl="/dashboard"` which is the v6 API. ClerkProvider already had `signInFallbackRedirectUrl="/dashboard"` correctly.

3. `top-bar.tsx` branding div had `cursor-pointer` but no onClick or Link — dead click target. Wrapped in `<Link href="/dashboard">` with hover opacity.

## Outcome

- ✅ Impact: New Chat on settings navigates to dashboard; sign-in redirects to dashboard; logo is a working link
- 🧪 Tests: Manual verification — test each flow after frontend hot-reload
- 📁 Files: 3 files changed (settings/page.tsx, sign-in/page.tsx, top-bar.tsx)
- 🔁 Next prompts: Check sign-up page for same `afterSignUpUrl` deprecation issue
- 🧠 Reflection: Clerk v6 silently dropped `afterSignInUrl`/`afterSignUpUrl` props — always verify SDK versions when redirect props don't work

## Evaluation notes (flywheel)

- Failure modes observed: Deprecated Clerk props silently ignored; no-op event handlers without user feedback
- Graders run and results (PASS/FAIL): manual pending
- Prompt variant (if applicable): null
- Next experiment: Also fix sign-up page if it uses afterSignUpUrl
