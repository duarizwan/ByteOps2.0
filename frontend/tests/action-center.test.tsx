import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import React from "react";

const navigationState = vi.hoisted(() => ({
    trace: "run-from-query",
}));

const agentRunState = vi.hoisted(() => ({
    runs: [
        {
            id: "run-from-query",
            conversation_id: null,
            intent: "workflow",
            status: "completed",
            plan: { summary: "Run workflow" },
            final_response: "Workflow completed.",
            error: null,
            metadata: { workflow_id: "workflow-1" },
            created_at: "2026-05-31T09:00:00.000Z",
            updated_at: "2026-05-31T09:00:02.000Z",
            completed_at: "2026-05-31T09:00:02.000Z",
            steps: [
                {
                    id: "step-1",
                    step_type: "tool_call",
                    name: "workflow_action:gmail",
                    status: "completed",
                    input: null,
                    output: { summary: "Summarized Gmail." },
                    error: null,
                    created_at: "2026-05-31T09:00:01.000Z",
                },
            ],
        },
    ],
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
    useSearchParams: () => ({
        get: (key: string) => (key === "trace" ? navigationState.trace : null),
    }),
}));

vi.mock("@/hooks/use-agent-runs", () => ({
    useAgentRuns: () => ({
        runs: agentRunState.runs,
        isLoading: false,
    }),
}));

vi.mock("@/components/cursor-glow", () => ({ CursorGlow: () => null }));
vi.mock("@/components/runs/graph-canvas", () => ({
    GraphCanvas: ({ selectedRunId, onLoad }: { selectedRunId: string | null; onLoad?: () => void }) => {
        React.useEffect(() => {
            onLoad?.();
        }, [onLoad]);
        return <div data-testid="graph-canvas" data-run-id={selectedRunId ?? ""} />;
    },
}));

import { ActionCenter } from "@/components/runs/action-center";

describe("ActionCenter", () => {
    it("opens the trace drawer from the trace query parameter", () => {
        render(<ActionCenter />);

        expect(screen.getByTestId("graph-canvas")).toHaveAttribute("data-run-id", "run-from-query");
        expect(screen.getByRole("button", { name: /back to action center/i })).toBeInTheDocument();
    });
});
