/**
 * useAgentRuns — fetches and manages agent run records.
 *
 * Polls every 30 seconds and exposes a manual refresh helper.
 * Errors are silently swallowed so the UI never crashes the page.
 *
 * Uses useAuth().getToken() (proper Clerk React hook) so that the token is
 * always valid for the current session — avoids the window.Clerk.session race
 * condition that causes 401 errors on first render.
 */
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@clerk/nextjs";

export interface AgentRunStep {
    id: string;
    step_type: "route" | "plan" | "tool_call" | "approval" | "verify" | "final";
    name: string;
    status: string;
    input: Record<string, unknown> | null;
    output: Record<string, unknown> | null;
    error: string | null;
    created_at: string;
}

export interface AgentRun {
    id: string;
    conversation_id: string | null;
    intent: string;
    status: "planning" | "waiting_approval" | "running" | "completed" | "failed" | "cancelled";
    plan: Record<string, unknown> | null;
    final_response: string | null;
    error: string | null;
    metadata?: Record<string, unknown> | null;
    created_at: string;
    updated_at: string;
    completed_at: string | null;
    steps: AgentRunStep[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const POLL_INTERVAL_MS = 30_000;

async function authFetch(
    path: string,
    getToken: () => Promise<string | null>,
    init: RequestInit = {}
): Promise<Response> {
    const token = await getToken();
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(init.headers as Record<string, string>),
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(`${API_BASE}${path}`, { ...init, headers });
}

export function useAgentRuns() {
    const { getToken } = useAuth();
    const [runs, setRuns] = useState<AgentRun[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetch_ = useCallback(async (silent = false) => {
        if (!silent) setIsLoading(true);
        try {
            const res = await authFetch("/api/agent-runs", getToken);
            if (res.ok) {
                const data: AgentRun[] = await res.json();
                setRuns(data);
                setError(null);
            } else {
                setError(`Failed to load runs (${res.status})`);
            }
        } catch {
            setError("Could not reach server — showing last known data");
        } finally {
            if (!silent) setIsLoading(false);
        }
    }, [getToken]);

    // Initial fetch + polling
    useEffect(() => {
        fetch_();
        intervalRef.current = setInterval(() => fetch_(true), POLL_INTERVAL_MS);
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [fetch_]);

    const refresh = useCallback(() => fetch_(), [fetch_]);

    return {
        runs,
        isLoading,
        error,
        refresh,
    };
}
