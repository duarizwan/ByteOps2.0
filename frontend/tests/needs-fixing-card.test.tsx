import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NeedsFixingCard } from "@/components/runs/needs-fixing-card";
import type { AgentRun } from "@/hooks/use-agent-runs";

function makeRun(overrides: Partial<AgentRun> = {}): AgentRun {
    return {
        id: "run-failed",
        conversation_id: null,
        intent: "gmail",
        status: "failed",
        plan: null,
        final_response: null,
        error: "HTTP 401 Unauthorized",
        metadata: null,
        created_at: "2026-05-31T10:00:00Z",
        updated_at: "2026-05-31T10:00:05Z",
        completed_at: null,
        steps: [
            {
                id: "s1",
                step_type: "tool_call",
                name: "send_email",
                status: "failed",
                input: { to: "alice@example.com", subject: "Update" },
                output: null,
                error: "HTTP 401 Unauthorized",
                created_at: "2026-05-31T10:00:01Z",
            },
        ],
        ...overrides,
    };
}

describe("NeedsFixingCard", () => {
    it("renders red status bar", () => {
        const { container } = render(<NeedsFixingCard run={makeRun()} />);
        const bar = container.querySelector("[data-status-bar]");
        expect(bar?.getAttribute("data-status")).toBe("failed");
    });

    it("renders platform badge", () => {
        render(<NeedsFixingCard run={makeRun()} />);
        expect(screen.getByText("Gmail")).toBeInTheDocument();
    });

    it("renders summary from summarizeAction as 'what failed' line", () => {
        render(<NeedsFixingCard run={makeRun()} />);
        expect(screen.getByText(/Sent email to alice@example\.com/)).toBeInTheDocument();
    });

    it("renders run.error text (truncated to 120 chars)", () => {
        render(<NeedsFixingCard run={makeRun()} />);
        expect(screen.getByText(/401 Unauthorized/)).toBeInTheDocument();
    });

    it("auth error: renders Reconnect link to /settings", () => {
        render(<NeedsFixingCard run={makeRun({ error: "HTTP 401 Unauthorized" })} />);
        const link = screen.getByRole("link", { name: /reconnect/i });
        expect(link).toHaveAttribute("href", "/settings");
    });

    it("timeout error: renders disabled Retry button", () => {
        render(<NeedsFixingCard run={makeRun({ error: "Request timeout after 30s" })} />);
        const btn = screen.getByRole("button", { name: /retry/i });
        expect(btn).toBeDisabled();
    });

    it("unknown error: no CTA rendered", () => {
        render(<NeedsFixingCard run={makeRun({ error: "Something went wrong" })} />);
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
    });

    it("null error: no CTA rendered", () => {
        render(<NeedsFixingCard run={makeRun({ error: null })} />);
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
    });
});
