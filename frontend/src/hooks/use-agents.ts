"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

export interface AgentTemplate {
    key: string;
    name: string;
    description: string;
    icon: string;
    color: string;
    required_tools: string[];
    optional_tools: string[];
    default_schedule: string;
    schedule_options: { value: string; label: string }[];
    config_schema: { key: string; label: string; type: string; default: unknown }[];
    capabilities: string[];
    available: boolean;
}

export interface HiredAgent {
    id: string;
    template_key: string;
    name: string;
    description: string | null;
    status: "active" | "paused" | "running" | "failed";
    config: Record<string, unknown>;
    schedule: string;
    last_run_at: string | null;
    next_run_at: string | null;
    last_error: string | null;
    total_runs: number;
    recent_runs: { id: string; intent: string; status: string; created_at: string; flagged: boolean }[];
    template: { name: string; icon: string; color: string; capabilities: string[] } | null;
    created_at: string | null;
}

export function useAgents() {
    const [templates, setTemplates] = useState<AgentTemplate[]>([]);
    const [agents, setAgents] = useState<HiredAgent[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        try {
            const [tmpl, agts] = await Promise.all([
                api<AgentTemplate[]>("/api/agents/templates"),
                api<HiredAgent[]>("/api/agents"),
            ]);
            setTemplates(tmpl);
            setAgents(agts);
            setError(null);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to load agents");
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        refresh();

        // Poll every 30s so status updates (running → active/failed) are visible
        const interval = setInterval(refresh, 30_000);

        // Also refresh when tab regains focus
        const onFocus = () => refresh();
        window.addEventListener("focus", onFocus);

        return () => {
            clearInterval(interval);
            window.removeEventListener("focus", onFocus);
        };
    }, [refresh]);

    const hire = useCallback(
        async (templateKey: string, name: string, config: Record<string, unknown>, schedule: string) => {
            const agent = await api<HiredAgent>("/api/agents", {
                method: "POST",
                body: JSON.stringify({ template_key: templateKey, name, config, schedule }),
            });
            await refresh();
            return agent;
        },
        [refresh]
    );

    const pause = useCallback(async (agentId: string) => {
        await api(`/api/agents/${agentId}/pause`, { method: "POST" });
        await refresh();
    }, [refresh]);

    const resume = useCallback(async (agentId: string) => {
        await api(`/api/agents/${agentId}/resume`, { method: "POST" });
        await refresh();
    }, [refresh]);

    const runNow = useCallback(async (agentId: string) => {
        await api(`/api/agents/${agentId}/run`, { method: "POST" });
        await refresh();
    }, [refresh]);

    const fire = useCallback(async (agentId: string) => {
        await api(`/api/agents/${agentId}`, { method: "DELETE" });
        await refresh();
    }, [refresh]);

    return { templates, agents, isLoading, error, refresh, hire, pause, resume, runNow, fire };
}
