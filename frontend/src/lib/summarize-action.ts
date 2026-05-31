import type { AgentRun, AgentRunStep } from "@/hooks/use-agent-runs";
import type { ActionSummary } from "./action-center-types";

const WRITE_VERBS = new Set([
    "send", "reply", "create", "update", "delete", "trash", "merge",
    "post", "upload", "move", "add", "write", "edit", "archive",
    "close", "reopen", "remove",
]);

function str(v: unknown, fallback = ""): string {
    return v != null ? String(v) : fallback;
}

function trunc(s: string, max: number): string {
    return s.length > max ? s.slice(0, max) : s;
}

function humanize(name: string): string {
    return name.replace(/_/g, " ");
}

export function getFirstCrudStep(run: AgentRun): AgentRunStep | undefined {
    return (run.steps ?? []).find(
        (s) => s.step_type === "tool_call" && WRITE_VERBS.has(s.name.split("_")[0].toLowerCase()),
    );
}

export function summarizeAction(run: AgentRun): ActionSummary {
    const step = getFirstCrudStep(run);

    if (!step) {
        const anyTool = (run.steps ?? []).find((s) => s.step_type === "tool_call");
        return {
            summary: `${run.intent} action completed`,
            detail: anyTool ? humanize(anyTool.name) : humanize(run.intent),
        };
    }

    const inp = (step.input ?? {}) as Record<string, unknown>;
    const n = step.name;

    // ── Gmail ──────────────────────────────────────────────────────────────────
    if (n === "send_email") return {
        summary: `Sent email to ${str(inp.to, "recipient")}`,
        detail: `Subject: ${str(inp.subject, "(no subject)")}`,
    };
    if (n === "reply_to_email") return {
        summary: `Replied to ${str(inp.thread_id, "thread")}`,
        detail: `To: ${str(inp.to, "recipient")}`,
    };
    if (n === "trash_email") return {
        summary: `Trashed email: ${str(inp.subject, "(no subject)")}`,
        detail: `${str(inp.count, "1")} message(s)`,
    };
    if (n === "create_draft") return {
        summary: `Saved draft for ${str(inp.to, "recipient")}`,
        detail: `Subject: ${str(inp.subject, "(no subject)")}`,
    };

    // ── Calendar ───────────────────────────────────────────────────────────────
    if (n === "create_event") {
        const attendees = Array.isArray(inp.attendees) ? inp.attendees.length : 0;
        return {
            summary: `Created event: ${str(inp.title, "event")}`,
            detail: `${str(inp.date, "")}${inp.date ? " · " : ""}${attendees} people`,
        };
    }
    if (n === "update_event") return {
        summary: `Updated event: ${str(inp.title, "event")}`,
        detail: str(inp.updated_fields, "details updated"),
    };
    if (n === "delete_event") return {
        summary: `Deleted event: ${str(inp.title, "event")}`,
        detail: str(inp.date, ""),
    };

    // ── Slack ──────────────────────────────────────────────────────────────────
    if (n === "send_message" || n === "post_message") return {
        summary: `Posted to #${str(inp.channel, "channel")}`,
        detail: trunc(str(inp.text, ""), 60),
    };

    // ── Jira ───────────────────────────────────────────────────────────────────
    if (n === "create_issue" && run.intent === "jira") return {
        summary: `Created ${str(inp.issue_type, "issue")} ${str(inp.key, "")}`.trimEnd(),
        detail: str(inp.summary, ""),
    };
    if (n === "update_issue") return {
        summary: `Updated ${str(inp.key, "issue")}`,
        detail: str(inp.updated_fields, "fields updated"),
    };
    if (n === "add_comment") return {
        summary: `Commented on ${str(inp.key, "issue")}`,
        detail: trunc(str(inp.body, ""), 60),
    };

    // ── GitHub ─────────────────────────────────────────────────────────────────
    if (n === "merge_pull_request") return {
        summary: `Merged PR #${str(inp.pull_number, "")}`,
        detail: str(inp.title, ""),
    };
    if (n === "create_issue" && run.intent === "github") return {
        summary: `Created issue #${str(inp.number, "")}`,
        detail: str(inp.title, ""),
    };

    // ── Dropbox ────────────────────────────────────────────────────────────────
    if (n === "upload_file") return {
        summary: `Uploaded ${str(inp.filename, "file")}`,
        detail: `to ${str(inp.path, "")}`,
    };
    if (n === "delete_file") return {
        summary: `Deleted ${str(inp.filename, "file")}`,
        detail: str(inp.path, ""),
    };
    if (n === "move_file") return {
        summary: `Moved ${str(inp.filename, "file")}`,
        detail: `to ${str(inp.destination, "")}`,
    };

    // ── Fallback ───────────────────────────────────────────────────────────────
    return {
        summary: `${run.intent} action completed`,
        detail: humanize(step.name),
    };
}
