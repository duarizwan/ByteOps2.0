import { describe, it, expect } from "vitest";
import { graphTransformer } from "@/lib/graph-transformer";
import type { AgentRun } from "@/hooks/use-agent-runs";

const run: AgentRun = {
    id: "r1",
    conversation_id: null,
    intent: "general",
    status: "completed",
    plan: null,
    final_response: "done",
    error: null,
    created_at: "",
    updated_at: "",
    completed_at: null,
    flagged: true,
    anomaly_score: 2.0,
    step_scores: { s1: 0.5, s2: 2.0 },
    steps: [
        { id: "s1", step_type: "tool_call", name: "search_emails", status: "completed", input: null, output: null, error: null, created_at: "" },
        { id: "s2", step_type: "tool_call", name: "forward_email", status: "completed", input: null, output: null, error: null, created_at: "" },
    ],
};

describe("graphTransformer anomaly heat", () => {
    it("normalizes step scores to 0..1 on nodes", () => {
        const { nodes } = graphTransformer(run);
        const s1 = nodes.find((n) => n.id === "s1");
        const s2 = nodes.find((n) => n.id === "s2");
        expect(s2?.data.anomalyScore).toBe(1);          // max score -> 1
        expect(s1?.data.anomalyScore).toBeCloseTo(0.25); // 0.5 / 2.0
    });

    it("leaves anomalyScore null when run is not flagged", () => {
        const { nodes } = graphTransformer({ ...run, flagged: false });
        const s2 = nodes.find((n) => n.id === "s2");
        expect(s2?.data.anomalyScore).toBeNull();
    });
});
