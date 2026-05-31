"use client";

import { Activity } from "lucide-react";
import { RunRow } from "./run-row";
import type { AgentRun } from "@/hooks/use-agent-runs";

interface RunsListPanelProps {
    runs: AgentRun[];
    isLoading: boolean;
    selectedRunId: string | null;
    onSelect: (id: string) => void;
    onDismiss: (id: string) => void;
    onClearAll: () => void;
}

interface DateGroup {
    label: string;
    runs: AgentRun[];
}

function dateSeparatorLabel(iso: string): string {
    const date = new Date(iso);
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterdayStart = new Date(todayStart.getTime() - 86_400_000);
    if (date >= todayStart) return "Today";
    if (date >= yesterdayStart) return "Yesterday";
    return date.toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" });
}

function groupByDate(runs: AgentRun[]): DateGroup[] {
    const groups: DateGroup[] = [];
    let currentLabel = "";
    for (const run of runs) {
        const label = dateSeparatorLabel(run.created_at);
        if (label !== currentLabel) {
            currentLabel = label;
            groups.push({ label, runs: [] });
        }
        groups[groups.length - 1].runs.push(run);
    }
    return groups;
}

export function RunsListPanel({
    runs,
    isLoading,
    selectedRunId,
    onSelect,
    onDismiss,
    onClearAll,
}: RunsListPanelProps) {
    const groups = groupByDate(runs);

    return (
        <div
            className="flex flex-col h-full"
            style={{ background: "var(--card)", borderRight: "1px solid var(--border)" }}
        >
            {/* Header */}
            <div style={{
                padding: "10px 12px 8px",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexShrink: 0,
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <Activity size={13} style={{ color: "var(--primary)" }} />
                    <span style={{
                        fontSize: 10,
                        fontWeight: 700,
                        letterSpacing: "0.08em",
                        textTransform: "uppercase",
                        color: "var(--muted-foreground)",
                    }}>
                        Runs
                    </span>
                    {runs.length > 0 && (
                        <span style={{
                            fontSize: 9.5,
                            fontWeight: 600,
                            padding: "1px 5px",
                            borderRadius: 4,
                            background: "color-mix(in srgb, var(--primary) 12%, transparent)",
                            color: "var(--primary)",
                        }}>
                            {runs.length}
                        </span>
                    )}
                </div>

                {runs.length > 0 && (
                    <button
                        onClick={onClearAll}
                        style={{
                            fontSize: 10,
                            color: "var(--muted-foreground)",
                            background: "none",
                            border: "none",
                            cursor: "pointer",
                            padding: "2px 6px",
                            borderRadius: 5,
                            transition: "color 0.12s",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = "var(--foreground)")}
                        onMouseLeave={(e) => (e.currentTarget.style.color = "var(--muted-foreground)")}
                    >
                        Clear all
                    </button>
                )}
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto" style={{ minHeight: 0, padding: "4px 6px" }}>
                {isLoading && runs.length === 0 ? (
                    <div className="flex items-center justify-center py-8">
                        <div
                            className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin"
                            style={{ borderColor: "var(--primary)", borderTopColor: "transparent" }}
                        />
                    </div>
                ) : runs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-10 px-4 text-center gap-2">
                        <Activity size={22} style={{ color: "var(--border)" }} />
                        <p style={{ fontSize: 11, color: "var(--muted-foreground)", lineHeight: 1.5 }}>
                            No agent runs yet. Send a message in chat to see traces here.
                        </p>
                    </div>
                ) : (
                    <div>
                        {groups.map((group) => (
                            <div key={group.label}>
                                <div style={{
                                    fontSize: 9.5,
                                    fontWeight: 700,
                                    letterSpacing: "0.07em",
                                    textTransform: "uppercase",
                                    color: "var(--muted-foreground)",
                                    opacity: 0.5,
                                    padding: "8px 8px 4px",
                                }}>
                                    {group.label}
                                </div>
                                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                                    {group.runs.map((run) => (
                                        <RunRow
                                            key={run.id}
                                            run={run}
                                            isSelected={run.id === selectedRunId}
                                            onSelect={() => onSelect(run.id)}
                                            onDismiss={() => onDismiss(run.id)}
                                        />
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
