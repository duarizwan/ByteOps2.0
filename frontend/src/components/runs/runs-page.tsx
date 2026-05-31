// Deprecated: superseded by ActionCenter — safe to delete after QA sign-off
"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Activity, List } from "lucide-react";
import { useAgentRuns, type AgentRun } from "@/hooks/use-agent-runs";
import { RunsListPanel } from "./runs-list-panel";
import { GraphCanvas } from "./graph-canvas";
import { CursorGlow } from "@/components/cursor-glow";

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

function useIsMobile() {
    const [isMobile, setIsMobile] = useState(false);
    useEffect(() => {
        const check = () => setIsMobile(window.innerWidth < 768);
        check();
        window.addEventListener("resize", check);
        return () => window.removeEventListener("resize", check);
    }, []);
    return isMobile;
}

export function RunsPage() {
    const router = useRouter();
    const isMobile = useIsMobile();
    const { runs, isLoading } = useAgentRuns();
    const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
    const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
    const [drawerOpen, setDrawerOpen] = useState(false);

    const visibleRuns = runs.filter((r) => !dismissedIds.has(r.id) && hasCrudOperation(r));

    const handleSelect = useCallback((id: string) => {
        setSelectedRunId(id);
        setDrawerOpen(false);
    }, []);

    const handleDismiss = useCallback((id: string) => {
        setDismissedIds((prev) => {
            const next = new Set(prev);
            next.add(id);
            return next;
        });
        setSelectedRunId((current) => {
            if (current !== id) return current;
            const remaining = runs.filter((r) => !dismissedIds.has(r.id) && r.id !== id);
            return remaining[0]?.id ?? null;
        });
    }, [runs, dismissedIds]);

    const handleClearAll = useCallback(() => {
        setDismissedIds(new Set(runs.map((r) => r.id)));
        setSelectedRunId(null);
    }, [runs]);

    return (
        <>
            <CursorGlow />

            {/* Top bar */}
            <div style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
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
                    <Activity size={14} style={{ color: "var(--primary)" }} />
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--foreground)", letterSpacing: "0.01em" }}>
                        Agent Runs
                    </span>
                </div>

                <span style={{ fontSize: 11, color: "var(--muted-foreground)", marginLeft: 2 }}>
                    Execution trace viewer
                </span>

                {/* Mobile: open drawer button */}
                {isMobile && (
                    <button
                        onClick={() => setDrawerOpen(true)}
                        style={{
                            marginLeft: "auto",
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                            padding: "5px 10px",
                            borderRadius: 8,
                            border: "1px solid var(--border)",
                            background: "var(--card)",
                            color: "var(--muted-foreground)",
                            fontSize: 12,
                            cursor: "pointer",
                        }}
                    >
                        <List size={13} />
                        Runs
                        {visibleRuns.length > 0 && (
                            <span style={{
                                background: "color-mix(in srgb, var(--primary) 15%, transparent)",
                                color: "var(--primary)",
                                borderRadius: 999,
                                fontSize: 10,
                                padding: "0 5px",
                                minWidth: 16,
                                textAlign: "center",
                            }}>
                                {visibleRuns.length}
                            </span>
                        )}
                    </button>
                )}
            </div>

            {/* Main split layout */}
            <div className="flex flex-1 overflow-hidden" style={{ minHeight: 0, position: "relative" }}>

                {/* Desktop sidebar */}
                {!isMobile && (
                    <div className="flex-shrink-0" style={{ width: 280 }}>
                        <RunsListPanel
                            runs={visibleRuns}
                            isLoading={isLoading}
                            selectedRunId={selectedRunId}
                            onSelect={handleSelect}
                            onDismiss={handleDismiss}
                            onClearAll={handleClearAll}
                        />
                    </div>
                )}

                {/* Graph canvas — full width on mobile */}
                <div className="flex-1 overflow-hidden relative">
                    <GraphCanvas selectedRunId={selectedRunId} />
                </div>

                {/* Mobile drawer overlay */}
                {isMobile && drawerOpen && (
                    <>
                        {/* Backdrop */}
                        <div
                            onClick={() => setDrawerOpen(false)}
                            style={{
                                position: "absolute",
                                inset: 0,
                                background: "rgba(0,0,0,0.6)",
                                zIndex: 40,
                            }}
                        />
                        {/* Drawer panel */}
                        <div style={{
                            position: "absolute",
                            top: 0,
                            left: 0,
                            bottom: 0,
                            width: "min(320px, 90vw)",
                            zIndex: 50,
                            display: "flex",
                            flexDirection: "column",
                        }}>
                            <RunsListPanel
                                runs={visibleRuns}
                                isLoading={isLoading}
                                selectedRunId={selectedRunId}
                                onSelect={handleSelect}
                                onDismiss={handleDismiss}
                                onClearAll={handleClearAll}
                            />
                        </div>
                    </>
                )}
            </div>
        </>
    );
}
