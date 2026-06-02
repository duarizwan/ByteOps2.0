/**
 * useWorkflows - fetches and manages workflow activity for the right panel.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";

export interface WorkflowItem {
    id: string;
    name: string;
    description: string | null;
    status: "active" | "paused" | "running" | "failed" | "waiting_approval";
    trigger: Record<string, unknown>;
    actions: unknown[];
    trigger_label: string;
    condition_summary: string;
    action_summary: string;
    action_count: number;
    approval_required?: boolean;
    approval_summary?: string;
    last_run_at: string | null;
    next_run_at: string | null;
    last_error: string | null;
    last_agent_run_id?: string | null;
    last_run_status?: string | null;
    last_run_summary?: string | null;
    consecutive_failure_count?: number;
    last_failure_at?: string | null;
    needs_attention?: boolean;
    created_at?: string | null;
    updated_at?: string | null;
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

export function useWorkflows() {
    const { getToken } = useAuth();
    const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetch_ = useCallback(async (silent = false) => {
        if (!silent) setIsLoading(true);
        try {
            const res = await authFetch("/api/workflows", getToken);
            if (res.ok) {
                const data: WorkflowItem[] = await res.json();
                setWorkflows(data);
                setError(null);
            } else {
                setError(`Failed to load workflows (${res.status})`);
            }
        } catch {
            setError("Could not reach server — showing last known data");
        } finally {
            if (!silent) setIsLoading(false);
        }
    }, [getToken]);

    useEffect(() => {
        fetch_();
        intervalRef.current = setInterval(() => fetch_(true), POLL_INTERVAL_MS);
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [fetch_]);

    const refresh = useCallback(() => fetch_(), [fetch_]);

    const replaceWorkflow = useCallback((updated: WorkflowItem) => {
        setWorkflows((prev) => prev.map((w) => (w.id === updated.id ? updated : w)));
    }, []);

    const pause = useCallback(async (id: string) => {
        const res = await authFetch(`/api/workflows/${id}/pause`, getToken, { method: "POST" });
        if (res.ok) replaceWorkflow(await res.json());
        else await fetch_(true);
    }, [fetch_, getToken, replaceWorkflow]);

    const resume = useCallback(async (id: string) => {
        const res = await authFetch(`/api/workflows/${id}/resume`, getToken, { method: "POST" });
        if (res.ok) replaceWorkflow(await res.json());
        else await fetch_(true);
    }, [fetch_, getToken, replaceWorkflow]);

    const runNow = useCallback(async (id: string) => {
        const res = await authFetch(`/api/workflows/${id}/run`, getToken, { method: "POST" });
        if (res.ok) replaceWorkflow(await res.json());
        else await fetch_(true);
    }, [fetch_, getToken, replaceWorkflow]);

    const deleteWorkflow = useCallback(async (id: string) => {
        const res = await authFetch(`/api/workflows/${id}`, getToken, { method: "DELETE" });
        if (res.ok) {
            setWorkflows((prev) => prev.filter((w) => w.id !== id));
        }
        // No fetch_(true) fallback on failure: deleted items are gone from the
        // server regardless; the next poll will reconcile if needed.
        return res.ok;
    }, [getToken]);

    return {
        workflows,
        isLoading,
        error,
        refresh,
        pause,
        resume,
        runNow,
        deleteWorkflow,
    };
}
