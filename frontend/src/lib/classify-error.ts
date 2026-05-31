import type { ActionErrorCategory } from "./action-center-types";

const AUTH_RE        = /401|403|token|expired|unauthorized/i;
const TIMEOUT_RE     = /timeout|503|api error/i;
const OAUTH_RE       = /oauth|not connected|not authenticated|integration.*required|reconnect/i;
const NO_RESULTS_RE  = /no results|no emails|nothing found|empty result/i;
const MCP_RE         = /mcp|tool.*unavailable|service.*unavailable|tool.*error/i;

export function classifyError(error: string | null): ActionErrorCategory {
    if (!error) return "unknown";
    if (OAUTH_RE.test(error))       return "oauth_missing";
    if (NO_RESULTS_RE.test(error))  return "no_results";
    if (AUTH_RE.test(error))        return "auth";
    if (TIMEOUT_RE.test(error))     return "timeout";
    if (MCP_RE.test(error))         return "mcp_unavailable";
    return "unknown";
}
