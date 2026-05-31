import { describe, it, expect } from "vitest";
import { summarizeAction } from "@/lib/summarize-action";
import type { AgentRun } from "@/hooks/use-agent-runs";

function makeRun(overrides: Partial<AgentRun> = {}): AgentRun {
    return {
        id: "run-1",
        conversation_id: null,
        intent: "gmail",
        status: "completed",
        plan: null,
        final_response: null,
        error: null,
        metadata: null,
        created_at: "2026-05-31T10:00:00Z",
        updated_at: "2026-05-31T10:00:05Z",
        completed_at: "2026-05-31T10:00:05Z",
        steps: [],
        ...overrides,
    };
}

function makeStep(name: string, input: Record<string, unknown> = {}) {
    return {
        id: `step-${name}`,
        step_type: "tool_call" as const,
        name,
        status: "completed",
        input,
        output: null,
        error: null,
        created_at: "2026-05-31T10:00:01Z",
    };
}

describe("summarizeAction", () => {
    // ── Gmail ──────────────────────────────────────────────────────────────────
    it("gmail send_email: summary + detail from input", () => {
        const run = makeRun({
            intent: "gmail",
            steps: [makeStep("send_email", { to: "bob@example.com", subject: "Hello" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Sent email to bob@example.com");
        expect(detail).toBe("Subject: Hello");
    });

    it("gmail reply_to_email: summary + detail from input", () => {
        const run = makeRun({
            intent: "gmail",
            steps: [makeStep("reply_to_email", { thread_id: "thread-42", to: "alice@example.com" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Replied to thread-42");
        expect(detail).toBe("To: alice@example.com");
    });

    it("gmail trash_email: summary + detail", () => {
        const run = makeRun({
            intent: "gmail",
            steps: [makeStep("trash_email", { subject: "Old newsletter", count: 3 })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Trashed email: Old newsletter");
        expect(detail).toBe("3 message(s)");
    });

    it("gmail create_draft: summary + detail", () => {
        const run = makeRun({
            intent: "gmail",
            steps: [makeStep("create_draft", { to: "ceo@acme.com", subject: "Q3 report" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Saved draft for ceo@acme.com");
        expect(detail).toBe("Subject: Q3 report");
    });

    // ── Calendar ───────────────────────────────────────────────────────────────
    it("calendar create_event: summary + detail", () => {
        const run = makeRun({
            intent: "calendar",
            steps: [makeStep("create_event", { title: "Team standup", date: "2026-06-01", attendees: ["a", "b", "c"] })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Created event: Team standup");
        expect(detail).toBe("2026-06-01 · 3 people");
    });

    it("calendar update_event: summary + detail", () => {
        const run = makeRun({
            intent: "calendar",
            steps: [makeStep("update_event", { title: "Sync", updated_fields: "time changed" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Updated event: Sync");
        expect(detail).toBe("time changed");
    });

    it("calendar delete_event: summary + detail", () => {
        const run = makeRun({
            intent: "calendar",
            steps: [makeStep("delete_event", { title: "Old meeting", date: "2026-05-30" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Deleted event: Old meeting");
        expect(detail).toBe("2026-05-30");
    });

    // ── Slack ──────────────────────────────────────────────────────────────────
    it("slack send_message: summary + detail", () => {
        const run = makeRun({
            intent: "slack",
            steps: [makeStep("send_message", { channel: "general", text: "Hello team, here is the update" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Posted to #general");
        expect(detail).toBe("Hello team, here is the update");
    });

    it("slack post_message: same as send_message", () => {
        const run = makeRun({
            intent: "slack",
            steps: [makeStep("post_message", { channel: "dev", text: "Deploy done" })],
        });
        const { summary } = summarizeAction(run);
        expect(summary).toBe("Posted to #dev");
    });

    // ── Jira ───────────────────────────────────────────────────────────────────
    it("jira create_issue: summary + detail", () => {
        const run = makeRun({
            intent: "jira",
            steps: [makeStep("create_issue", { issue_type: "Bug", key: "PROJ-42", summary: "Login fails" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Created Bug PROJ-42");
        expect(detail).toBe("Login fails");
    });

    it("jira update_issue: summary + detail", () => {
        const run = makeRun({
            intent: "jira",
            steps: [makeStep("update_issue", { key: "PROJ-10", updated_fields: "priority → High" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Updated PROJ-10");
        expect(detail).toBe("priority → High");
    });

    it("jira add_comment: summary + detail (truncated)", () => {
        const run = makeRun({
            intent: "jira",
            steps: [makeStep("add_comment", { key: "PROJ-5", body: "Fixed in this commit" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Commented on PROJ-5");
        expect(detail).toBe("Fixed in this commit");
    });

    // ── GitHub ─────────────────────────────────────────────────────────────────
    it("github merge_pull_request: summary + detail", () => {
        const run = makeRun({
            intent: "github",
            steps: [makeStep("merge_pull_request", { pull_number: 99, title: "Add dark mode" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Merged PR #99");
        expect(detail).toBe("Add dark mode");
    });

    it("github create_issue: summary + detail", () => {
        const run = makeRun({
            intent: "github",
            steps: [makeStep("create_issue", { number: 12, title: "Fix nav bug" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Created issue #12");
        expect(detail).toBe("Fix nav bug");
    });

    // ── Dropbox ────────────────────────────────────────────────────────────────
    it("dropbox upload_file: summary + detail", () => {
        const run = makeRun({
            intent: "dropbox",
            steps: [makeStep("upload_file", { filename: "report.pdf", path: "/docs/reports" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Uploaded report.pdf");
        expect(detail).toBe("to /docs/reports");
    });

    it("dropbox delete_file: summary + detail", () => {
        const run = makeRun({
            intent: "dropbox",
            steps: [makeStep("delete_file", { filename: "old.csv", path: "/archive" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Deleted old.csv");
        expect(detail).toBe("/archive");
    });

    it("dropbox move_file: summary + detail", () => {
        const run = makeRun({
            intent: "dropbox",
            steps: [makeStep("move_file", { filename: "data.csv", destination: "/processed" })],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBe("Moved data.csv");
        expect(detail).toBe("to /processed");
    });

    // ── Fallbacks ──────────────────────────────────────────────────────────────
    it("missing step.input fields: fallback strings, no crash", () => {
        const run = makeRun({
            intent: "gmail",
            steps: [makeStep("send_email", {})],
        });
        const { summary, detail } = summarizeAction(run);
        expect(summary).toBeTruthy();
        expect(detail).toBeTruthy();
        expect(typeof summary).toBe("string");
        expect(typeof detail).toBe("string");
    });

    it("no matching CRUD step: generic fallback", () => {
        const run = makeRun({
            intent: "slack",
            steps: [
                { id: "s1", step_type: "route", name: "intent_router", status: "completed", input: null, output: null, error: null, created_at: "2026-05-31T10:00:00Z" },
            ],
        });
        const { summary } = summarizeAction(run);
        expect(summary).toMatch(/slack/i);
    });

    it("empty steps: generic fallback using intent", () => {
        const run = makeRun({ intent: "jira", steps: [] });
        const { summary } = summarizeAction(run);
        expect(summary).toMatch(/jira/i);
    });

    it("slack message text truncated to 60 chars in detail", () => {
        const longText = "A".repeat(80);
        const run = makeRun({
            intent: "slack",
            steps: [makeStep("send_message", { channel: "general", text: longText })],
        });
        const { detail } = summarizeAction(run);
        expect(detail.length).toBeLessThanOrEqual(60);
    });

    it("jira add_comment body truncated to 60 chars in detail", () => {
        const longBody = "B".repeat(80);
        const run = makeRun({
            intent: "jira",
            steps: [makeStep("add_comment", { key: "X-1", body: longBody })],
        });
        const { detail } = summarizeAction(run);
        expect(detail.length).toBeLessThanOrEqual(60);
    });
});
