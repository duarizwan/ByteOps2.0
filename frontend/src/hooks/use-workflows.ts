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
    status: "active" | "paused" | "running" | "failed";
    trigger: Record<string, unknown>;
    actions: unknown[];
    trigger_label: string;
    action_summary: string;
    last_run_at: string | null;
    next_run_at: string | null;
    last_error: string | null;
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
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetch_ = useCallback(async (silent = false) => {
        if (!silent) setIsLoading(true);
        try {
            const res = await authFetch("/api/workflows", getToken);
            if (res.ok) {
                const data: WorkflowItem[] = await res.json();
                setWorkflows(data);
            }
        } catch {
            // Keep stale data if the network blips.
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

    return {
        workflows,
        isLoading,
        refresh,
        pause,
        resume,
        runNow,
    };
}
