import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TraceDrawer } from "@/components/runs/trace-drawer";
import type { AgentRun } from "@/hooks/use-agent-runs";

vi.mock("@/components/runs/graph-canvas", () => ({
    GraphCanvas: ({ selectedRunId }: { selectedRunId: string | null }) => (
        <div data-testid="graph-canvas" data-run-id={selectedRunId} />
    ),
}));

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

describe("TraceDrawer", () => {
    it("renders nothing when run is null", () => {
        const { container } = render(<TraceDrawer run={null} onClose={vi.fn()} />);
        expect(container.firstChild).toBeNull();
    });

    it("renders full-screen drawer when run is provided", () => {
        const { container } = render(<TraceDrawer run={makeRun()} onClose={vi.fn()} />);
        const drawer = container.querySelector("[data-drawer]");
        expect(drawer).toBeInTheDocument();
        expect(drawer?.getAttribute("data-open")).toBe("true");
        expect(screen.getByTestId("graph-canvas")).toBeInTheDocument();
    });

    it("renders run summary in header", () => {
        render(<TraceDrawer run={makeRun()} onClose={vi.fn()} />);
        expect(screen.getByText(/Sent email to bob@example\.com/)).toBeInTheDocument();
    });

    it("back button fires onClose", () => {
        const onClose = vi.fn();
        render(<TraceDrawer run={makeRun()} onClose={onClose} />);
        fireEvent.click(screen.getByRole("button", { name: /back to action center/i }));
        expect(onClose).toHaveBeenCalledOnce();
    });

    it("no backdrop — full-screen overlay has no click-away dismiss", () => {
        const { container } = render(<TraceDrawer run={makeRun()} onClose={vi.fn()} />);
        expect(container.querySelector("[data-backdrop]")).toBeNull();
    });
});
