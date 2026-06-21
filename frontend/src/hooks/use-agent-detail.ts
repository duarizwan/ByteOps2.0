"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { HiredAgent } from "@/hooks/use-agents";

export interface AgentRun {
    id: string;
    status: string;
    intent: string;
    created_at: string | null;
    flagged: boolean;
    anomaly_score: number | null;
    summary: string | null;
    error: string | null;
}

export function useAgentDetail(id: string) {
    const [agent, setAgent] = useState<HiredAgent | null>(null);
    const [runs, setRuns] = useState<AgentRun[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        try {
            const [agentData, runsData] = await Promise.all([
                api<HiredAgent>(`/api/agents/${id}`),
                api<AgentRun[]>(`/api/agents/${id}/runs`),
            ]);
            setAgent(agentData);
            setRuns(runsData);
            setError(null);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to load agent");
        } finally {
            setIsLoading(false);
        }
    }, [id]);

    useEffect(() => {
        refresh();
        const interval = setInterval(refresh, 30_000);
        const onFocus = () => refresh();
        window.addEventListener("focus", onFocus);
        return () => {
            clearInterval(interval);
            window.removeEventListener("focus", onFocus);
        };
    }, [refresh]);

    const pause = useCallback(async () => {
        await api(`/api/agents/${id}/pause`, { method: "POST" });
        await refresh();
    }, [id, refresh]);

    const resume = useCallback(async () => {
        await api(`/api/agents/${id}/resume`, { method: "POST" });
        await refresh();
    }, [id, refresh]);

    const runNow = useCallback(async () => {
        await api(`/api/agents/${id}/run`, { method: "POST" });
        await refresh();
    }, [id, refresh]);

    return { agent, runs, isLoading, error, refresh, pause, resume, runNow };
}
