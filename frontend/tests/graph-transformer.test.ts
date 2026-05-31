import { describe, it, expect } from "vitest";
import { graphTransformer } from "../src/lib/graph-transformer";
import type { AgentRun } from "../src/hooks/use-agent-runs";

function makeRun(overrides: Partial<AgentRun> = {}): AgentRun {
    return {
        id: "run-1",
        intent: "gmail",
        status: "completed",
        plan: null,
        final_response: "Done",
        error: null,
        created_at: "2026-05-30T10:00:00Z",
        updated_at: "2026-05-30T10:00:05Z",
        completed_at: "2026-05-30T10:00:05Z",
        steps: [],
        ...overrides,
    };
}

function makeStep(
    id: string,
    step_type: AgentRun["steps"][number]["step_type"],
    name: string,
    overrides: Partial<AgentRun["steps"][number]> = {}
): AgentRun["steps"][number] {
    return {
        id,
        step_type,
        name,
        status: "completed",
        input: null,
        output: null,
        error: null,
        created_at: "2026-05-30T10:00:01Z",
        ...overrides,
    };
}

describe("graphTransformer", () => {
    it("empty steps → produces user_input + final_response synthetic nodes", () => {
        const { nodes, edges } = graphTransformer(makeRun({ steps: [] }));
        expect(nodes.length).toBe(2);
        expect(nodes[0].data.nodeType).toBe("user_input");
        expect(nodes[1].data.nodeType).toBe("final_response");
    });

    it("empty steps → one edge connecting the two synthetic nodes", () => {
        const { nodes, edges } = graphTransformer(makeRun({ steps: [] }));
        expect(edges.length).toBe(1);
        expect(edges[0].source).toBe(nodes[0].id);
        expect(edges[0].target).toBe(nodes[1].id);
    });

    it("route step → intent_router node", () => {
        const run = makeRun({ steps: [makeStep("s1", "route", "intent_router")] });
        const { nodes } = graphTransformer(run);
        const routeNode = nodes.find((n) => n.id === "s1");
        expect(routeNode?.data.nodeType).toBe("intent_router");
    });

    it("plan step → agent_plan node", () => {
        const run = makeRun({ steps: [makeStep("s1", "plan", "agent_plan")] });
        const { nodes } = graphTransformer(run);
        const planNode = nodes.find((n) => n.id === "s1");
        expect(planNode?.data.nodeType).toBe("agent_plan");
    });

    it("tool_call step → tool_call node", () => {
        const run = makeRun({ steps: [makeStep("s1", "tool_call", "search_emails")] });
        const { nodes } = graphTransformer(run);
        const toolNode = nodes.find((n) => n.id === "s1");
        expect(toolNode?.data.nodeType).toBe("tool_call");
    });

    it("tool_call with platform name → platform_api node", () => {
        const run = makeRun({ steps: [makeStep("s1", "tool_call", "gmail_send")] });
        const { nodes } = graphTransformer(run);
        const node = nodes.find((n) => n.id === "s1");
        expect(node?.data.nodeType).toBe("platform_api");
    });

    it("final step → final_response node (no extra synthetic final appended)", () => {
        const run = makeRun({ steps: [makeStep("s1", "final", "final_response")] });
        const { nodes } = graphTransformer(run);
        const finalNodes = nodes.filter((n) => n.data.nodeType === "final_response");
        expect(finalNodes.length).toBe(1);
        expect(finalNodes[0].id).toBe("s1");
    });

    it("failed step → node has status failed", () => {
        const run = makeRun({
            status: "failed",
            steps: [makeStep("s1", "tool_call", "search_emails", { status: "failed", error: "timeout" })],
        });
        const { nodes } = graphTransformer(run);
        const toolNode = nodes.find((n) => n.id === "s1");
        expect(toolNode?.data.status).toBe("failed");
        expect(toolNode?.data.error).toBe("timeout");
    });

    it("steps are chained with directed edges", () => {
        const run = makeRun({
            steps: [
                makeStep("s1", "route", "intent_router"),
                makeStep("s2", "plan", "agent_plan"),
            ],
        });
        const { nodes, edges } = graphTransformer(run);
        // user_input → s1 → s2 → final_response
        expect(edges.length).toBe(3);
        const s1s2 = edges.find((e) => e.source === "s1" && e.target === "s2");
        expect(s1s2).toBeDefined();
    });

    it("two consecutive tool_call steps have distinct x positions (parallel layout)", () => {
        const run = makeRun({
            steps: [
                makeStep("t1", "tool_call", "search_emails"),
                makeStep("t2", "tool_call", "list_labels"),
            ],
        });
        const { nodes } = graphTransformer(run);
        const t1 = nodes.find((n) => n.id === "t1")!;
        const t2 = nodes.find((n) => n.id === "t2")!;
        // Parallel nodes should be at the same y but different x
        expect(t1.position.y).toBeCloseTo(t2.position.y, 0);
        expect(t1.position.x).not.toBeCloseTo(t2.position.x, 0);
    });

    it("all nodes have dagre-assigned positions (non-zero coordinates)", () => {
        const run = makeRun({
            steps: [
                makeStep("s1", "route", "intent_router"),
                makeStep("s2", "plan", "agent_plan"),
                makeStep("s3", "tool_call", "search_emails"),
            ],
        });
        const { nodes } = graphTransformer(run);
        nodes.forEach((n) => {
            expect(typeof n.position.x).toBe("number");
            expect(typeof n.position.y).toBe("number");
        });
    });

    it("node label uses step name in monospace-friendly format", () => {
        const run = makeRun({ steps: [makeStep("s1", "tool_call", "search_emails")] });
        const { nodes } = graphTransformer(run);
        const node = nodes.find((n) => n.id === "s1")!;
        expect(node.data.label).toBe("search_emails");
    });

    it("node has typeColor set based on type", () => {
        const run = makeRun({ steps: [makeStep("s1", "route", "intent_router")] });
        const { nodes } = graphTransformer(run);
        const node = nodes.find((n) => n.id === "s1")!;
        expect(node.data.typeColor).toBeTruthy();
    });
});
