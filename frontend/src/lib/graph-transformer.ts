import dagre from "@dagrejs/dagre";
import type { AgentRun, AgentRunStep } from "@/hooks/use-agent-runs";

// ── Types ──────────────────────────────────────────────────────────────────

export type GraphNodeType =
    | "user_input"
    | "intent_router"
    | "agent_plan"
    | "tool_call"
    | "platform_api"
    | "approval_gate"
    | "verify"
    | "final_response";

export type RiskLevel = "READ" | "WRITE" | "DESTRUCTIVE" | "EXTERNAL_SEND" | "NONE";

export interface GraphNodeData {
    [key: string]: unknown;
    label: string;
    sublabel: string;
    nodeType: GraphNodeType;
    riskLevel: RiskLevel;
    durationMs: number | null;
    status: string;
    input: Record<string, unknown> | null;
    output: Record<string, unknown> | null;
    error: string | null;
    // Border color for this node type (hex)
    typeColor: string;
    // Background color for this node type (hex)
    bgColor: string;
    // Whether border is dashed
    borderDashed: boolean;
}

export interface GraphNode {
    id: string;
    type: "graphnode";
    position: { x: number; y: number };
    data: GraphNodeData;
    width: number;
    height: number;
    draggable: true;
}

export interface GraphEdge {
    id: string;
    source: string;
    target: string;
    type: "default";
    markerEnd: { type: "arrowclosed"; color: string };
    style: { stroke: string; strokeWidth: number };
}

// ── Constants ──────────────────────────────────────────────────────────────

const NODE_WIDTH  = 210;
const NODE_HEIGHT = 72;
const RANKSEP = 48;
const NODESEP = 80;

// Type-specific border colors (match graph-v2 mockup)
export const TYPE_COLOR: Record<GraphNodeType, string> = {
    user_input:    "#3B82F6",
    intent_router: "#22C55E",
    agent_plan:    "#A855F7",
    tool_call:     "#F59E0B",
    platform_api:  "#10B981",
    approval_gate: "#F97316",
    verify:        "#A855F7",
    final_response:"#22C55E",
};

// Exact dark background per node type (match graph-v2 mockup)
export const TYPE_BG_COLOR: Record<GraphNodeType, string> = {
    user_input:    "#0D1B2E",
    intent_router: "#091A12",
    agent_plan:    "#130D20",
    tool_call:     "#1C1508",
    platform_api:  "#071A12",
    approval_gate: "#1A0A00",
    verify:        "#130D20",
    final_response:"#091A12",
};

// Label colors (lighter shade of the border color for readability)
export const TYPE_LABEL_COLOR: Record<GraphNodeType, string> = {
    user_input:    "#93C5FD",
    intent_router: "#86EFAC",
    agent_plan:    "#D8B4FE",
    tool_call:     "#FCD34D",
    platform_api:  "#6EE7B7",
    approval_gate: "#FDBA74",
    verify:        "#D8B4FE",
    final_response:"#86EFAC",
};

export const BORDER_DASHED: Record<GraphNodeType, boolean> = {
    user_input:    false,
    intent_router: false,
    agent_plan:    false,
    tool_call:     false,
    platform_api:  true,
    approval_gate: true,
    verify:        false,
    final_response:false,
};

const RISK_BY_TYPE: Record<GraphNodeType, RiskLevel> = {
    user_input:    "NONE",
    intent_router: "NONE",
    agent_plan:    "NONE",
    tool_call:     "READ",
    platform_api:  "EXTERNAL_SEND",
    approval_gate: "DESTRUCTIVE",
    verify:        "NONE",
    final_response:"NONE",
};

const PLATFORM_KEYWORDS = ["gmail", "slack", "github", "jira", "calendar", "dropbox", "_api"];

const STEP_NAME_MAP: Record<string, string> = {
    intent_routing:                "Router",
    gmail_agent:                   "Gmail",
    calendar_agent:                "Calendar",
    github_agent:                  "GitHub",
    slack_agent:                   "Slack",
    jira_agent:                    "Jira",
    dropbox_agent:                 "Dropbox",
    workflow_draft_needs_review:   "Workflow Draft",
    workflow_created:              "Workflow Created",
    workflow_draft_approved:       "Draft Approved",
    workflow_creation_response:    "Workflow Created",
};

function humanizeStepName(name: string): string {
    if (STEP_NAME_MAP[name]) return STEP_NAME_MAP[name];
    return name
        .replace(/_tool$/, "")           // strip trailing _tool suffix
        .replace(/_/g, " ")              // underscores → spaces
        .replace(/\b\w/g, (c) => c.toUpperCase()); // Title Case
}

// ── Helpers ────────────────────────────────────────────────────────────────

function stepTypeToNodeType(step: AgentRunStep): GraphNodeType {
    switch (step.step_type) {
        case "route":    return "intent_router";
        case "plan":     return "agent_plan";
        case "approval": return "approval_gate";
        case "verify":   return "verify";
        case "final":    return "final_response";
        case "tool_call": {
            const nameLower = step.name.toLowerCase();
            return PLATFORM_KEYWORDS.some((kw) => nameLower.includes(kw))
                ? "platform_api"
                : "tool_call";
        }
    }
}

function buildSublabel(nodeType: GraphNodeType, step: AgentRunStep | null, run: AgentRun): string {
    if (!step) {
        // synthetic nodes
        if (nodeType === "user_input") return run.intent;
        if (nodeType === "final_response") return run.status === "failed" ? "failed" : "done";
        return "";
    }
    switch (nodeType) {
        case "intent_router": return `detected → ${run.intent}`;
        case "agent_plan":    return "executing plan";
        case "tool_call":     return `READ · ${step.status}`;
        case "platform_api":  return step.status === "failed" ? "error" : "ok";
        case "approval_gate": return step.status === "completed" ? "approved" : "awaiting";
        case "verify":        return step.status;
        case "final_response":return `done · ${run.status}`;
        default:              return "";
    }
}

function makeNode(
    id: string,
    nodeType: GraphNodeType,
    label: string,
    sublabel: string,
    step: AgentRunStep | null,
    run: AgentRun
): GraphNode {
    return {
        id,
        type: "graphnode",
        position: { x: 0, y: 0 },
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        draggable: true,
        data: {
            label,
            sublabel,
            nodeType,
            riskLevel: RISK_BY_TYPE[nodeType],
            durationMs: null,
            status: step?.status ?? (run.status === "failed" ? "failed" : "completed"),
            input: step?.input ?? null,
            output: step?.output ?? null,
            error: step?.error ?? null,
            typeColor: TYPE_COLOR[nodeType],
            bgColor: TYPE_BG_COLOR[nodeType],
            borderDashed: BORDER_DASHED[nodeType],
        },
    };
}

function makeEdge(source: string, target: string, dashed = false): GraphEdge {
    return {
        id: `edge-${source}-${target}`,
        source,
        target,
        type: "default",
        markerEnd: { type: "arrowclosed", color: dashed ? "#64748b" : "#475569" },
        style: {
            stroke: dashed ? "#64748b" : "#475569",
            strokeWidth: 2,
        },
    };
}

function detectParallelBands(steps: AgentRunStep[]): number[][] {
    const bands: number[][] = [];
    let i = 0;
    while (i < steps.length) {
        if (steps[i].step_type === "tool_call") {
            const band: number[] = [i];
            while (i + 1 < steps.length && steps[i + 1].step_type === "tool_call") {
                i++;
                band.push(i);
            }
            bands.push(band);
        } else {
            bands.push([i]);
        }
        i++;
    }
    return bands;
}

// ── Main transformer ───────────────────────────────────────────────────────

export function graphTransformer(run: AgentRun): { nodes: GraphNode[]; edges: GraphEdge[] } {
    // ── Zero-steps fallback ───────────────────────────────────────────────
    if ((run.steps ?? []).length === 0) {
        const userInputId = "user-input";
        const terminalId = "terminal";
        const isFailed = run.status === "failed";
        const terminalLabel = isFailed ? "Run Failed" : "No Steps";
        const terminalSub = run.error ?? (isFailed ? "failed" : run.status);
        const simpleNodes = [
            makeNode(userInputId, "user_input", "User Message", run.intent, null, run),
            makeNode(terminalId, "final_response", terminalLabel, terminalSub, null, run),
        ];
        const simpleEdges = [makeEdge(userInputId, terminalId)];
        const g = new dagre.graphlib.Graph();
        g.setDefaultEdgeLabel(() => ({}));
        g.setGraph({ rankdir: "TB", ranksep: RANKSEP, nodesep: NODESEP });
        simpleNodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
        simpleEdges.forEach((e) => g.setEdge(e.source, e.target));
        dagre.layout(g);
        return {
            nodes: simpleNodes.map((n) => {
                const pos = g.node(n.id);
                return { ...n, position: { x: pos ? pos.x - NODE_WIDTH / 2 : 0, y: pos ? pos.y - NODE_HEIGHT / 2 : 0 } };
            }),
            edges: simpleEdges,
        };
    }

    const nodes: GraphNode[] = [];
    const edges: GraphEdge[] = [];

    // 1 — Synthetic user_input
    const userInputId = "user-input";
    nodes.push(makeNode(userInputId, "user_input", "User Message",
        run.intent, null, run));

    // 2 — Map steps → nodes
    run.steps.forEach((step) => {
        const nodeType = stepTypeToNodeType(step);
        const sublabel = buildSublabel(nodeType, step, run);
        nodes.push(makeNode(step.id, nodeType, step.name, sublabel, step, run));
    });

    // 3 — Parallel band detection
    const bands = detectParallelBands(run.steps);

    // 4 — Synthetic final_response (only if no FINAL step)
    const hasFinalStep = run.steps.some((s) => s.step_type === "final");
    const finalNodeId = hasFinalStep ? null : "final-response";
    if (finalNodeId) {
        nodes.push(makeNode(finalNodeId, "final_response", "Final Response",
            run.status === "failed" ? "failed" : `done · ${run.status}`, null, run));
    }

    // 5 — Build raw edges (approval nodes included in chain for now)
    const firstStepId = run.steps.length > 0 ? run.steps[0].id : (finalNodeId ?? null);
    if (firstStepId) edges.push(makeEdge(userInputId, firstStepId));

    for (let bi = 0; bi < bands.length; bi++) {
        const band = bands[bi];
        const nextBand = bands[bi + 1];

        if (band.length === 1) {
            if (nextBand) {
                edges.push(makeEdge(run.steps[band[0]].id, run.steps[nextBand[0]].id));
            }
        } else {
            const prevId = bi > 0
                ? run.steps[bands[bi - 1][bands[bi - 1].length - 1]].id
                : userInputId;
            for (const idx of band) {
                edges.push(makeEdge(prevId, run.steps[idx].id));
            }
            if (nextBand) {
                for (const idx of band) {
                    edges.push(makeEdge(run.steps[idx].id, run.steps[nextBand[0]].id));
                }
            } else if (finalNodeId) {
                for (const idx of band) {
                    edges.push(makeEdge(run.steps[idx].id, finalNodeId));
                }
            }
        }
    }

    if (finalNodeId && run.steps.length > 0) {
        const lastBand = bands[bands.length - 1];
        if (lastBand.length === 1) {
            edges.push(makeEdge(run.steps[lastBand[0]].id, finalNodeId));
        }
    }

    // 5b — Style edges touching approval nodes as dashed (approval stays in main flow)
    const approvalIds = new Set(
        nodes.filter((n) => n.data.nodeType === "approval_gate").map((n) => n.id)
    );
    const routedEdges = approvalIds.size > 0
        ? edges.map((e) =>
            approvalIds.has(e.target) || approvalIds.has(e.source)
                ? makeEdge(e.source, e.target, true)
                : e
          )
        : edges;

    // 6 — Dagre layout
    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: "TB", ranksep: RANKSEP, nodesep: NODESEP });
    nodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
    routedEdges.forEach((e) => g.setEdge(e.source, e.target));
    dagre.layout(g);

    const positioned = nodes.map((n) => {
        const pos = g.node(n.id);
        return {
            ...n,
            position: {
                x: pos ? pos.x - NODE_WIDTH / 2 : 0,
                y: pos ? pos.y - NODE_HEIGHT / 2 : 0,
            },
        };
    });

    return { nodes: positioned, edges: routedEdges };
}
