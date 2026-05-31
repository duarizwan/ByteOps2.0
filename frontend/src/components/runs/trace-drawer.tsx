"use client";

import { useState, useEffect, useCallback } from "react";
import {
    ArrowLeft,
    Activity,
    Clock,
    Wrench,
    ShieldCheck,
    CheckCircle2,
    XCircle,
    Loader2,
    AlertCircle,
    Info,
} from "lucide-react";
import type { AgentRun } from "@/hooks/use-agent-runs";
import { GraphCanvas } from "./graph-canvas";

interface TraceDrawerProps {
    run: AgentRun | null;
    onClose: () => void;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatDuration(createdAt: string, completedAt: string | null): string {
    if (!completedAt) return "Running…";
    const ms = new Date(completedAt).getTime() - new Date(createdAt).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
}

function capitalize(s: string): string {
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function intentLabel(intent: string): string {
    const MAP: Record<string, string> = {
        gmail: "Gmail",
        calendar: "Calendar",
        github: "GitHub",
        slack: "Slack",
        jira: "Jira",
        dropbox: "Dropbox",
        workflow: "Workflow",
        general: "General",
    };
    return MAP[intent.toLowerCase()] ?? capitalize(intent);
}

function statusMeta(status: AgentRun["status"]): {
    label: string;
    color: string;
    bg: string;
    border: string;
    Icon: React.ElementType;
} {
    switch (status) {
        case "completed":
            return { label: "Completed", color: "#16A34A", bg: "rgba(34,197,94,0.08)", border: "rgba(34,197,94,0.3)", Icon: CheckCircle2 };
        case "failed":
            return { label: "Failed", color: "#DC2626", bg: "rgba(239,68,68,0.08)", border: "rgba(239,68,68,0.3)", Icon: XCircle };
        case "waiting_approval":
            return { label: "Pending Approval", color: "#CA8A04", bg: "rgba(234,179,8,0.08)", border: "rgba(234,179,8,0.3)", Icon: ShieldCheck };
        case "running":
        case "planning":
            return { label: "Running", color: "#2563EB", bg: "rgba(59,130,246,0.08)", border: "rgba(59,130,246,0.3)", Icon: Loader2 };
        default:
            return { label: capitalize(status), color: "var(--muted-foreground)", bg: "var(--muted)", border: "var(--border)", Icon: Info };
    }
}

function finalOutcome(run: AgentRun): string {
    if (run.final_response) {
        const clean = run.final_response
            .replace(/[*|\-]/g, " ")
            .replace(/\s+/g, " ")
            .trim();
        return clean.length > 120 ? clean.slice(0, 120) + "…" : clean;
    }
    if (run.error) {
        const clean = run.error.replace(/\s+/g, " ").trim();
        return clean.length > 120 ? clean.slice(0, 120) + "…" : clean;
    }
    if (run.status === "waiting_approval") return "Waiting for user approval before proceeding.";
    if (run.status === "running" || run.status === "planning") return "Execution in progress…";
    return "No outcome recorded.";
}

// ── Summary Card ───────────────────────────────────────────────────────────────

function ExecutionSummaryCard({ run }: { run: AgentRun }) {
    const sm = statusMeta(run.status);
    const StatusIcon = sm.Icon;
    const toolCalls = (run.steps ?? []).filter((s) => s.step_type === "tool_call").length;
    const approvals = (run.steps ?? []).filter((s) => s.step_type === "approval").length;
    const duration = formatDuration(run.created_at, run.completed_at);
    const outcome = finalOutcome(run);
    const isRunning = run.status === "running" || run.status === "planning";

    return (
        <div style={{
            margin: "12px 16px 0",
            borderRadius: 12,
            border: "1px solid var(--border)",
            background: "var(--card)",
            overflow: "hidden",
            flexShrink: 0,
        }}>
            {/* Top accent strip matching status color */}
            <div style={{ height: 3, background: sm.color, opacity: 0.7 }} />

            <div style={{ padding: "12px 16px 14px" }}>
                {/* Row 1 — Status + Intent */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
                    {/* Status badge */}
                    <span style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 5,
                        padding: "3px 10px",
                        borderRadius: 999,
                        fontSize: 11.5,
                        fontWeight: 600,
                        color: sm.color,
                        background: sm.bg,
                        border: `1px solid ${sm.border}`,
                    }}>
                        <StatusIcon size={12} className={isRunning ? "animate-spin" : ""} />
                        {sm.label}
                    </span>

                    {/* Divider */}
                    <span style={{ width: 1, height: 14, background: "var(--border)", flexShrink: 0 }} />

                    {/* Intent badge */}
                    <span style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 5,
                        padding: "3px 10px",
                        borderRadius: 999,
                        fontSize: 11.5,
                        fontWeight: 500,
                        color: "var(--primary)",
                        background: "color-mix(in srgb, var(--primary) 10%, transparent)",
                        border: "1px solid color-mix(in srgb, var(--primary) 25%, transparent)",
                    }}>
                        <Activity size={11} />
                        {intentLabel(run.intent)}
                    </span>
                </div>

                {/* Row 2 — Stat pills */}
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
                    {/* Duration */}
                    <StatPill icon={<Clock size={11} />} label="Duration" value={duration} />
                    {/* Tool Calls */}
                    <StatPill icon={<Wrench size={11} />} label="Tool Calls" value={String(toolCalls)} />
                    {/* Approvals */}
                    <StatPill
                        icon={<ShieldCheck size={11} />}
                        label="Approvals"
                        value={approvals > 0 ? `${approvals} required` : "None"}
                        highlight={approvals > 0}
                    />
                </div>

                {/* Row 3 — Final Outcome */}
                <div style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 6,
                    padding: "8px 10px",
                    borderRadius: 8,
                    background: run.status === "failed"
                        ? "color-mix(in srgb, var(--destructive) 5%, var(--background))"
                        : "var(--background)",
                    border: "1px solid var(--border)",
                }}>
                    <AlertCircle
                        size={12}
                        style={{
                            flexShrink: 0,
                            marginTop: 1,
                            color: run.status === "failed" ? "var(--destructive)" : "var(--muted-foreground)",
                        }}
                    />
                    <div>
                        <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--muted-foreground)", marginBottom: 2 }}>
                            Final Outcome
                        </p>
                        <p style={{
                            fontSize: 12,
                            color: run.status === "failed" ? "var(--destructive)" : "var(--foreground)",
                            lineHeight: 1.45,
                        }}>
                            {outcome}
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

function StatPill({ icon, label, value, highlight }: {
    icon: React.ReactNode;
    label: string;
    value: string;
    highlight?: boolean;
}) {
    return (
        <div style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            padding: "4px 10px",
            borderRadius: 8,
            fontSize: 11.5,
            border: "1px solid var(--border)",
            background: highlight ? "color-mix(in srgb, var(--warning) 8%, var(--card))" : "var(--card)",
            color: highlight ? "var(--warning)" : "var(--muted-foreground)",
        }}>
            <span style={{ opacity: 0.7, display: "flex", alignItems: "center" }}>{icon}</span>
            <span style={{ color: "var(--muted-foreground)" }}>{label}:</span>
            <span style={{
                fontWeight: 600,
                color: highlight ? "var(--warning)" : "var(--foreground)",
            }}>
                {value}
            </span>
        </div>
    );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function TraceDrawer({ run, onClose }: TraceDrawerProps) {
    const [isGraphReady, setIsGraphReady] = useState(false);
    const handleGraphLoad = useCallback(() => setIsGraphReady(true), []);

    useEffect(() => {
        setIsGraphReady(false);
    }, [run?.id]);

    if (!run) return null;

    return (
        <div
            data-drawer
            data-open="true"
            style={{
                position: "fixed",
                inset: 0,
                zIndex: 50,
                display: "flex",
                flexDirection: "column",
                background: "var(--background)",
            }}
        >
            {/* ── Header bar ─────────────────────────────────────────────────── */}
            <div style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "9px 16px",
                borderBottom: "1px solid var(--border)",
                background: "var(--background)",
                flexShrink: 0,
            }}>
                <button
                    aria-label="Back to Execution Trace"
                    onClick={onClose}
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
                        flexShrink: 0,
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
                    Execution Trace
                </button>

                <div style={{ width: 1, height: 16, background: "var(--border)" }} />

                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <Activity size={14} style={{ color: "var(--primary)" }} />
                    <span style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "var(--foreground)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    }}>
                        Run …{run.id.slice(-8)}
                    </span>
                </div>

                <span style={{
                    marginLeft: "auto",
                    fontSize: 11,
                    color: "var(--muted-foreground)",
                }}>
                    {new Date(run.created_at).toLocaleString(undefined, {
                        month: "short", day: "numeric",
                        hour: "numeric", minute: "2-digit",
                    })}
                </span>
            </div>

            {/* ── Execution Summary Card ──────────────────────────────────────── */}
            <ExecutionSummaryCard run={run} />

            {/* ── Graph canvas ────────────────────────────────────────────────── */}
            <div style={{ flex: 1, overflow: "hidden", position: "relative", marginTop: 12 }}>
                {!isGraphReady && (
                    <div
                        style={{
                            position: "absolute",
                            inset: 0,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            background: "var(--background)",
                            zIndex: 1,
                        }}
                    >
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                            <div style={{
                                width: 32,
                                height: 32,
                                border: "2px solid var(--border)",
                                borderTop: "2px solid var(--primary)",
                                borderRadius: "50%",
                            }} className="animate-spin" />
                            <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>Loading trace…</span>
                        </div>
                    </div>
                )}
                <GraphCanvas
                    selectedRunId={run.id}
                    onLoad={handleGraphLoad}
                />
            </div>
        </div>
    );
}
