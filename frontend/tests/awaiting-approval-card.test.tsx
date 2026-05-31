import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AwaitingApprovalCard } from "@/components/runs/awaiting-approval-card";
import type { AgentRun } from "@/hooks/use-agent-runs";

vi.mock("@/lib/api", () => ({
    api: vi.fn().mockResolvedValue({ status: "approved" }),
}));

function makeRun(overrides: Partial<AgentRun> = {}): AgentRun {
    return {
        id: "run-pending",
        conversation_id: null,
        intent: "gmail",
        status: "waiting_approval",
        plan: null,
        final_response: null,
        error: null,
        metadata: null,
        created_at: "2026-05-31T10:00:00Z",
        updated_at: "2026-05-31T10:00:00Z",
        completed_at: null,
        steps: [
            {
                id: "s1",
                step_type: "tool_call",
                name: "send_email",
                status: "pending",
                input: { to: "boss@example.com", subject: "Q3 summary" },
                output: null,
                error: null,
                created_at: "2026-05-31T10:00:00Z",
            },
        ],
        ...overrides,
    };
}

describe("AwaitingApprovalCard", () => {
    it("renders amber status bar", () => {
        const { container } = render(
            <AwaitingApprovalCard run={makeRun()} onApproved={vi.fn()} onCancelled={vi.fn()} />,
        );
        const bar = container.querySelector("[data-status-bar]");
        expect(bar).toBeInTheDocument();
        expect(bar?.getAttribute("data-status")).toBe("waiting_approval");
    });

    it("renders platform badge", () => {
        render(<AwaitingApprovalCard run={makeRun()} onApproved={vi.fn()} onCancelled={vi.fn()} />);
        expect(screen.getByText("Gmail")).toBeInTheDocument();
    });

    it("renders summary from summarizeAction", () => {
        render(<AwaitingApprovalCard run={makeRun()} onApproved={vi.fn()} onCancelled={vi.fn()} />);
        expect(screen.getByText(/Sent email to boss@example\.com/)).toBeInTheDocument();
    });

    it("renders Approve button", () => {
        render(<AwaitingApprovalCard run={makeRun()} onApproved={vi.fn()} onCancelled={vi.fn()} />);
        expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
    });

    it("renders Cancel button", () => {
        render(<AwaitingApprovalCard run={makeRun()} onApproved={vi.fn()} onCancelled={vi.fn()} />);
        expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    });

    it("renders Edit in chat link pointing to /dashboard", () => {
        render(<AwaitingApprovalCard run={makeRun()} onApproved={vi.fn()} onCancelled={vi.fn()} />);
        const link = screen.getByRole("link", { name: /edit in chat/i });
        expect(link).toBeInTheDocument();
        expect(link).toHaveAttribute("href", "/dashboard");
    });

    it("Approve button calls onApproved with run.id after success", async () => {
        const { api } = await import("@/lib/api");
        vi.mocked(api).mockResolvedValueOnce({ status: "approved" });

        const onApproved = vi.fn();
        render(<AwaitingApprovalCard run={makeRun()} onApproved={onApproved} onCancelled={vi.fn()} />);
        fireEvent.click(screen.getByRole("button", { name: /approve/i }));
        await waitFor(() => expect(onApproved).toHaveBeenCalledWith("run-pending"));
    });

    it("Cancel button calls onCancelled with run.id after success", async () => {
        const { api } = await import("@/lib/api");
        vi.mocked(api).mockResolvedValueOnce({ status: "cancelled" });

        const onCancelled = vi.fn();
        render(<AwaitingApprovalCard run={makeRun()} onApproved={vi.fn()} onCancelled={onCancelled} />);
        fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
        await waitFor(() => expect(onCancelled).toHaveBeenCalledWith("run-pending"));
    });

    it("409 on approve treated as stale — still calls onApproved", async () => {
        const { api } = await import("@/lib/api");
        vi.mocked(api).mockRejectedValueOnce(Object.assign(new Error("conflict"), { status: 409 }));

        const onApproved = vi.fn();
        render(<AwaitingApprovalCard run={makeRun()} onApproved={onApproved} onCancelled={vi.fn()} />);
        fireEvent.click(screen.getByRole("button", { name: /approve/i }));
        await waitFor(() => expect(onApproved).toHaveBeenCalledWith("run-pending"));
    });
});
