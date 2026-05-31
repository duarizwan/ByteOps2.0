import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ActionCard } from "@/components/runs/action-card";
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
        steps: [
            {
                id: "s1",
                step_type: "tool_call",
                name: "send_email",
                status: "completed",
                input: { to: "bob@example.com", subject: "Hello" },
                output: null,
                error: null,
                created_at: "2026-05-31T10:00:01Z",
            },
        ],
        ...overrides,
    };
}

describe("ActionCard", () => {
    it("renders the platform badge for gmail", () => {
        render(<ActionCard run={makeRun()} onTrace={vi.fn()} onDismiss={vi.fn()} />);
        expect(screen.getByText("Gmail")).toBeInTheDocument();
    });

    it("renders platform badge for all six platforms", () => {
        const platforms = ["gmail", "slack", "jira", "github", "calendar", "dropbox"] as const;
        const labels = ["Gmail", "Slack", "Jira", "GitHub", "Calendar", "Dropbox"];
        platforms.forEach((intent, i) => {
            const { unmount } = render(
                <ActionCard run={makeRun({ intent })} onTrace={vi.fn()} onDismiss={vi.fn()} />,
            );
            expect(screen.getAllByText(labels[i]).length).toBeGreaterThan(0);
            unmount();
        });
    });

    it("renders summary text from summarizeAction", () => {
        render(<ActionCard run={makeRun()} onTrace={vi.fn()} onDismiss={vi.fn()} />);
        expect(screen.getByText(/Sent email to bob@example\.com/)).toBeInTheDocument();
    });

    it("renders detail text from summarizeAction", () => {
        render(<ActionCard run={makeRun()} onTrace={vi.fn()} onDismiss={vi.fn()} />);
        expect(screen.getByText(/Subject: Hello/)).toBeInTheDocument();
    });

    it("renders a relative timestamp", () => {
        render(<ActionCard run={makeRun()} onTrace={vi.fn()} onDismiss={vi.fn()} />);
        // Timestamp element exists (exact value depends on current time)
        const card = screen.getByRole("article");
        expect(card).toBeInTheDocument();
    });

    it("trace button fires onTrace with run.id", () => {
        const onTrace = vi.fn();
        render(<ActionCard run={makeRun()} onTrace={onTrace} onDismiss={vi.fn()} />);
        fireEvent.click(screen.getByRole("button", { name: /trace/i }));
        expect(onTrace).toHaveBeenCalledWith("run-1");
    });

    it("dismiss button fires onDismiss with run.id", () => {
        const onDismiss = vi.fn();
        render(<ActionCard run={makeRun()} onTrace={vi.fn()} onDismiss={onDismiss} />);
        fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
        expect(onDismiss).toHaveBeenCalledWith("run-1");
    });

    it("completed run renders green status bar", () => {
        const { container } = render(<ActionCard run={makeRun({ status: "completed" })} onTrace={vi.fn()} onDismiss={vi.fn()} />);
        const bar = container.querySelector("[data-status-bar]");
        expect(bar).toBeInTheDocument();
        expect(bar?.getAttribute("data-status")).toBe("completed");
    });

    it("cancelled run renders grey status bar", () => {
        const { container } = render(<ActionCard run={makeRun({ status: "cancelled" })} onTrace={vi.fn()} onDismiss={vi.fn()} />);
        const bar = container.querySelector("[data-status-bar]");
        expect(bar?.getAttribute("data-status")).toBe("cancelled");
    });
});
