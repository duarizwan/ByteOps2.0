"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Zap } from "lucide-react";
import { useAgentRuns, type AgentRun } from "@/hooks/use-agent-runs";
import type { FilterTab, CategorizedRuns } from "@/lib/action-center-types";
import { ActionCard } from "./action-card";
import { AwaitingApprovalCard } from "./awaiting-approval-card";
import { NeedsFixingCard } from "./needs-fixing-card";
import { TraceDrawer } from "./trace-drawer";
import { FilterTabs } from "./filter-tabs";
import { CursorGlow } from "@/components/cursor-glow";

// ── Shared helpers ─────────────────────────────────────────────────────────────

const WRITE_VERBS = new Set([
    "send", "reply", "create", "update", "delete", "trash", "merge",
    "post", "upload", "move", "add", "write", "edit", "archive",
    "close", "reopen", "remove",
]);

function hasCrudOperation(run: AgentRun): boolean {
    if (run.status === "waiting_approval") return true;
    return (run.steps ?? []).some((step) => {
        if (step.step_type !== "tool_call") return false;
        return WRITE_VERBS.has(step.name.split("_")[0].toLowerCase());
    });
}

function categorize(runs: AgentRun[], tab: FilterTab, dismissedIds: Set<string>): CategorizedRuns {
    const visible = runs.filter((r) => !dismissedIds.has(r.id));
    const pending = visible.filter((r) => r.status === "waiting_approval");
    const failed  = visible.filter((r) => r.status === "failed");
    const history = visible.filter((r) => r.status === "completed" || r.status === "cancelled" || r.status === "running" || r.status === "planning");

    if (tab === "pending") return { pending, failed: [], history: [] };
    if (tab === "failed")  return { pending: [], failed, history: [] };
    return { pending, failed, history };
}

// ── Date grouping ──────────────────────────────────────────────────────────────

function isoDateLabel(iso: string): string {
    const d = new Date(iso);
    const today = new Date();
    const todayStr = today.toISOString().slice(0, 10);
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    const yStr = yesterday.toISOString().slice(0, 10);
    const dStr = d.toISOString().slice(0, 10);

    if (dStr === todayStr) return "Today";
    if (dStr === yStr) return "Yesterday";
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function groupByDate(runs: AgentRun[]): Array<{ label: string; runs: AgentRun[] }> {
    const groups: Map<string, AgentRun[]> = new Map();
    for (const run of runs) {
        const label = isoDateLabel(run.created_at);
        if (!groups.has(label)) groups.set(label, []);
        groups.get(label)!.push(run);
    }
    return Array.from(groups.entries()).map(([label, r]) => ({ label, runs: r }));
}

// ── Sub-sections ───────────────────────────────────────────────────────────────

function SectionHeader({ label, color }: { label: string; color: string }) {
    return (
        <p style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color,
            marginBottom: 6,
        }}>
            {label}
        </p>
    );
}

// ── Skeleton ───────────────────────────────────────────────────────────────────

function ActionCardSkeleton() {
    return (
        <div className="animate-pulse" style={{
            display: "flex",
            borderRadius: 8,
            overflow: "hidden",
            border: "1px solid var(--border)",
            background: "var(--card)",
            opacity: 0.6,
        }}>
            {/* Status bar placeholder */}
            <div style={{ width: 3, flexShrink: 0, background: "var(--border)" }} />
            {/* Body */}
            <div style={{ flex: 1, minWidth: 0, padding: "10px 12px", display: "flex", gap: 10, alignItems: "flex-start" }}>
                {/* Platform badge placeholder */}
                <div style={{ width: 44, height: 18, borderRadius: 5, background: "var(--border)", flexShrink: 0, marginTop: 1 }} />
                {/* Text placeholder */}
                <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ height: 10, borderRadius: 4, background: "var(--border)", width: "60%" }} />
                    <div style={{ height: 10, borderRadius: 4, background: "var(--border)", width: "80%" }} />
                    <div style={{ height: 9,  borderRadius: 4, background: "var(--border)", width: "40%" }} />
                </div>
                {/* Right column placeholder */}
                <div style={{ width: 36, display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
                    <div style={{ width: 18, height: 18, borderRadius: 4, background: "var(--border)" }} />
                    <div style={{ width: 24, height: 8,  borderRadius: 4, background: "var(--border)" }} />
                    <div style={{ width: 36, height: 18, borderRadius: 5, background: "var(--border)" }} />
                </div>
            </div>
        </div>
    );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function ActionCenter() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { runs, isLoading } = useAgentRuns();

    const [filterTab, setFilterTab]   = useState<FilterTab>("all");
    const [traceRunId, setTraceRunId] = useState<string | null>(null);
    const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
    const traceParam = searchParams.get("trace");

    useEffect(() => {
        if (traceParam) setTraceRunId(traceParam);
    }, [traceParam]);

    const visibleRuns = runs.filter(hasCrudOperation);
    const { pending, failed, history } = categorize(visibleRuns, filterTab, dismissedIds);
    const dateGroups = groupByDate(history);

    const dismiss = useCallback((id: string) => {
        setDismissedIds((prev) => new Set([...prev, id]));
    }, []);

    const traceRun = traceRunId ? runs.find((r) => r.id === traceRunId) ?? null : null;

    return (
        <>
            <CursorGlow />

            {/* Top bar */}
            <div style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "9px 16px",
                borderBottom: "1px solid var(--border)",
                background: "var(--background)",
                backdropFilter: "blur(12px)",
                flexShrink: 0,
                zIndex: 10,
            }}>
                <button
                    onClick={() => router.push("/dashboard")}
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        padding: "5px 12px",
                        borderRadius: 8,
                        border: "1px solid var(--border)",
                        background: "var(--card)",
                        color: "var(--muted-foreground)",
                        fontSize: 12,
                        fontWeight: 500,
                        cursor: "pointer",
                        transition: "border-color 0.15s, color 0.15s",
                    }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = "var(--primary)";
                        e.currentTarget.style.color = "var(--primary)";
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = "var(--border)";
                        e.currentTarget.style.color = "var(--muted-foreground)";
                    }}
                >
                    <ArrowLeft size={13} />
                    Dashboard
                </button>

                <div style={{ width: 1, height: 16, background: "var(--border)" }} />

                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <Zap size={14} style={{ color: "var(--primary)" }} />
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--foreground)" }}>
                        Action Center
                    </span>
                </div>

                <div style={{ marginLeft: "auto" }}>
                    <FilterTabs active={filterTab} onChange={setFilterTab} />
                </div>
            </div>

            {/* Feed */}
            <div style={{
                flex: 1,
                overflowY: "auto",
                padding: "16px 20px",
                display: "flex",
                flexDirection: "column",
                gap: 16,
            }}>
                {/* Skeleton loading state — only on initial empty load */}
                {isLoading && runs.length === 0 && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <ActionCardSkeleton />
                        <ActionCardSkeleton />
                        <ActionCardSkeleton />
                    </div>
                )}

                {/* Awaiting Approval */}
                {pending.length > 0 && (
                    <section>
                        <SectionHeader label="Awaiting Approval" color="#EAB308" />
                        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                            {pending.map((run) => (
                                <AwaitingApprovalCard
                                    key={run.id}
                                    run={run}
                                    onApproved={dismiss}
                                    onCancelled={dismiss}
                                />
                            ))}
                        </div>
                    </section>
                )}

                {filterTab === "pending" && pending.length === 0 && !isLoading && (
                    <p style={{ fontSize: 13, color: "var(--muted-foreground)", textAlign: "center", marginTop: 40 }}>
                        No pending approvals right now.
                    </p>
                )}

                {/* Needs Fixing */}
                {failed.length > 0 && (
                    <section>
                        <SectionHeader label="Needs Fixing" color="#EF4444" />
                        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                            {failed.map((run) => (
                                <NeedsFixingCard key={run.id} run={run} />
                            ))}
                        </div>
                    </section>
                )}

                {filterTab === "failed" && failed.length === 0 && !isLoading && (
                    <p style={{ fontSize: 13, color: "var(--muted-foreground)", textAlign: "center", marginTop: 40 }}>
                        No failed actions.
                    </p>
                )}

                {/* Action Feed */}
                {filterTab !== "pending" && filterTab !== "failed" && (
                    <>
                        {dateGroups.length === 0 && !isLoading && pending.length === 0 && failed.length === 0 && (
                            <p style={{
                                fontSize: 13,
                                color: "var(--muted-foreground)",
                                textAlign: "center",
                                marginTop: 40,
                            }}>
                                No agent runs yet. Send a message in chat to see your AI&apos;s actions here.
                            </p>
                        )}

                        {dateGroups.length > 0 && (
                            <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 4 }}>
                                <button
                                    onClick={() => {
                                        history.forEach((r) => dismiss(r.id));
                                    }}
                                    style={{
                                        fontSize: 11,
                                        color: "var(--muted-foreground)",
                                        background: "none",
                                        border: "1px solid var(--border)",
                                        borderRadius: 6,
                                        padding: "3px 10px",
                                        cursor: "pointer",
                                    }}
                                    onMouseEnter={(e) => { e.currentTarget.style.color = "var(--foreground)"; }}
                                    onMouseLeave={(e) => { e.currentTarget.style.color = "var(--muted-foreground)"; }}
                                >
                                    Clear all
                                </button>
                            </div>
                        )}

                        {dateGroups.map(({ label, runs: groupRuns }) => (
                            <section key={label}>
                                <p style={{
                                    fontSize: 10,
                                    fontWeight: 700,
                                    letterSpacing: "0.08em",
                                    textTransform: "uppercase",
                                    color: "var(--muted-foreground)",
                                    marginBottom: 6,
                                }}>
                                    {label}
                                </p>
                                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                                    {groupRuns.map((run) => (
                                        <ActionCard
                                            key={run.id}
                                            run={run}
                                            onTrace={setTraceRunId}
                                            onDismiss={dismiss}
                                        />
                                    ))}
                                </div>
                            </section>
                        ))}
                    </>
                )}
            </div>

            {/* Trace drawer */}
            <TraceDrawer
                run={traceRun}
                onClose={() => setTraceRunId(null)}
            />
        </>
    );
}
