"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import type { AgentRun } from "./use-agent-runs";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useAgentRun(runId: string | null) {
    const { getToken } = useAuth();
    const [run, setRun] = useState<AgentRun | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchRun = useCallback(async (id: string) => {
        setIsLoading(true);
        setError(null);
        try {
            const token = await getToken();
            const headers: Record<string, string> = { "Content-Type": "application/json" };
            if (token) headers["Authorization"] = `Bearer ${token}`;
            const res = await fetch(`${API_BASE}/api/agent-runs/${id}`, { headers });
            if (res.status === 404) {
                setError("Run not found or unavailable.");
                setRun(null);
            } else if (!res.ok) {
                setError("Failed to load run details.");
                setRun(null);
            } else {
                const data: AgentRun = await res.json();
                setRun(data);
            }
        } catch {
            setError("Network error — could not load run.");
            setRun(null);
        } finally {
            setIsLoading(false);
        }
    }, [getToken]);

    useEffect(() => {
        if (!runId) {
            setRun(null);
            setError(null);
            return;
        }
        fetchRun(runId);
    }, [runId, fetchRun]);

    return { run, isLoading, error };
}
