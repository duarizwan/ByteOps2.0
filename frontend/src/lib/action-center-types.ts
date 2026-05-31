import type { AgentRun } from "@/hooks/use-agent-runs";

export interface ActionSummary {
    summary: string;
    detail: string;
}

export type ActionErrorCategory = "auth" | "timeout" | "oauth_missing" | "no_results" | "mcp_unavailable" | "backend_down" | "unknown";

export type FilterTab = "all" | "pending" | "failed";

export interface CategorizedRuns {
    pending: AgentRun[];
    failed: AgentRun[];
    history: AgentRun[];
}
