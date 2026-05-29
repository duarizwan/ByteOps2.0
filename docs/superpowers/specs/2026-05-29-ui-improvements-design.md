# UI Polish — Design Spec
**Date:** 2026-05-29  
**Status:** Approved  
**Scope:** Frontend polish across TopBar, CollapsibleSidebar, ChatInterface, ContextPanel

---

## 1. Problem Statement

Four concrete issues were identified during review:

1. **Header redundancy** — The brand name "ByteOps" appears in both the `<h1>` and the subtitle (`"AI Work Assistant · ByteOps"`), creating visual noise.
2. **Logo mark is plain** — A white box with a text `b` is inconsistent with the gradient-icon treatment on the landing page.
3. **No visual hierarchy for connected tools** — Connected tools in the sidebar show the same flat green dot as the landing-page chips. No glow or weight distinguishes them from disconnected.
4. **Minor polish gaps** — Message animations are abrupt, tab labels disappear too early, and the textarea is fixed-height.

---

## 2. In Scope

| # | Component | Change |
|---|-----------|--------|
| H1 | `top-bar.tsx` | Remove `· ByteOps` from subtitle → `"AI Work Assistant"` |
| H2 | `top-bar.tsx` | Replace plain white-box logo with gradient `rounded-xl` + `Sparkles` icon (matches landing page) |
| H3 | `top-bar.tsx` | Add `hover:scale-[0.98]` to logo link for subtle press feel |
| S1 | `collapsible-sidebar.tsx` | `getStatusColor`: connected returns `bg-success` + green glow shadow; disconnected stays `bg-muted-foreground` |
| S2 | `collapsible-sidebar.tsx` | Status dot gets `transition-all duration-300` for smooth glow on/off |
| C0 | `chat-interface.tsx` | AI avatar: replace `<Sparkles>` icon with a bold `b` text mark (same gradient-ai background) — Sparkles reserved for top-bar logo |
| C1 | `chat-interface.tsx` | Each new message bubble gets `animate-in fade-in slide-in-from-bottom-2 duration-300` |
| C2 | `chat-interface.tsx` | Typing indicator dots get staggered `animation-delay` (0ms / 150ms / 300ms) for wave effect |
| C3 | `chat-interface.tsx` | Textarea auto-grows on input up to `max-h-36` (≈6 rows), resets to `min-h-[44px]` on send |
| P1 | `context-panel.tsx` | Tab labels: `hidden xl:inline` → `hidden lg:inline` |
| SB1 | `collapsible-sidebar.tsx` | Conversation list: `max-h-64 overflow-y-auto` → `flex-1 overflow-y-auto` |

## 3. Out of Scope

- `window.confirm` → inline delete confirmation (deferred — requires more state)
- Context-aware header subtitle (deferred — needs conversation state threading)
- Any backend changes

---

## 4. Component-Level Design

### 4.1 `top-bar.tsx` — Header

**Before:**
```tsx
<div className="w-9 h-9 rounded-lg ... bg-white border border-border dark:bg-black">
  <span className="font-bold text-base ...">b</span>
</div>
<h1>ByteOps</h1>
<p>AI Work Assistant · ByteOps</p>
```

**After:**
```tsx
<div className="w-9 h-9 rounded-xl flex items-center justify-center bg-gradient-to-br from-blue-700 to-blue-500">
  <Sparkles className="w-4 h-4 text-white" />
</div>
<h1>ByteOps</h1>
<p>AI Work Assistant</p>
```

Logo link gets `hover:scale-[0.98] transition-transform duration-150`.

---

### 4.2 `collapsible-sidebar.tsx` — Connected Tool Glow

**Before:**
```ts
if (isConnected(toolId)) return "bg-success";
return "bg-muted-foreground";
```

**After:**
```ts
if (isConnected(toolId))
  return "bg-success shadow-[0_0_6px_2px_rgba(34,197,94,0.45)] transition-all duration-300";
return "bg-muted-foreground transition-all duration-300";
```

The dot element gets `transition-all duration-300` baked in via the returned class string so the glow smoothly appears/disappears when connection state changes.

**Conversation list** — remove `max-h-64`, replace with `flex-1` on the outer section so the list fills available sidebar height.

---

### 4.3 `chat-interface.tsx` — Animations + Auto-grow Textarea

**Message appear animation:**  
`tailwindcss-animate` is **not** installed. Use a CSS keyframe defined in `globals.css` instead:
```css
@keyframes messageIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.message-in {
  animation: messageIn 0.25s ease-out both;
}
```
Each message `<div>` gets the `message-in` class.

**Typing indicator stagger:**  
Three dots currently all use `animate-pulse` with no delay. Add `style={{ animationDelay: "0ms" }}`, `"150ms"`, `"300ms"` to each dot respectively.

**Auto-grow textarea:**  
Replace `rows={2}` with `rows={1}` and add an `onInput` handler:
```ts
const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
  e.target.style.height = "auto";
  e.target.style.height = Math.min(e.target.scrollHeight, 144) + "px";
};
```
Reset height to `"auto"` after send. Apply `min-h-[44px] max-h-36 resize-none` via className.

---

### 4.4 `context-panel.tsx` — Tab Labels

Single class change: `hidden xl:inline` → `hidden lg:inline` on each tab label `<span>`.

---

## 5. Acceptance Criteria

- [ ] "ByteOps" appears exactly once in the top bar (in the `<h1>`)
- [ ] Logo mark is a gradient blue rounded square with Sparkles icon
- [ ] Connected tools show a green dot with visible glow; disconnected show a plain grey dot
- [ ] Glow fades in/out smoothly (no flash) when tool connection state changes
- [ ] New chat messages slide up and fade in
- [ ] Typing dots animate in a wave pattern (staggered, not all-at-once)
- [ ] Chat textarea grows as user types, up to 6 rows
- [ ] Context panel tab labels are visible at `lg` (1024px) breakpoint
- [ ] Conversation list in sidebar uses available height (not capped at 256px)

---

## 6. Files Changed

- `frontend/src/components/dashboard/top-bar.tsx`
- `frontend/src/components/dashboard/collapsible-sidebar.tsx`
- `frontend/src/components/dashboard/chat-interface.tsx`
- `frontend/src/components/dashboard/context-panel.tsx`

---

## 7. Risks

- Auto-grow textarea height reset must happen after React re-render; a `useEffect` watching `input` state may be needed if the `onInput` approach races.
- `tailwindcss-animate` is confirmed **not installed** — the CSS keyframe approach in globals.css is the correct path.
