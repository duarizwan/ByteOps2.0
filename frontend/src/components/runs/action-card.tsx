"use client";

import type { AgentRun } from "@/hooks/use-agent-runs";
import { summarizeAction } from "@/lib/summarize-action";

const BADGE: Record<string, { bg: string; text: string; label: string }> = {
    gmail:    { bg: "rgba(239,68,68,.14)",   text: "#F87171", label: "Gmail"    },
    slack:    { bg: "rgba(168,85,247,.12)",  text: "#C084FC", label: "Slack"    },
    jira:     { bg: "rgba(59,130,246,.12)",  text: "#60A5FA", label: "Jira"     },
    github:   { bg: "rgba(107,114,128,.12)", text: "#9CA3AF", label: "GitHub"   },
    calendar: { bg: "rgba(34,197,94,.12)",   text: "#4ADE80", label: "Calendar" },
    dropbox:  { bg: "rgba(14,165,233,.12)",  text: "#38BDF8", label: "Dropbox"  },
};

const STATUS_BAR: Record<string, string> = {
    completed:        "#22C55E",
    cancelled:        "var(--muted-foreground)",
    failed:           "#F87171",
    running:          "#60A5FA",
    planning:         "#60A5FA",
    waiting_approval: "#EAB308",
};

const STATUS_BADGE: Record<string, { label: string; bg: string; text: string }> = {
    completed:        { label: "Completed",       bg: "rgba(34,197,94,.15)",   text: "#22C55E" },
    waiting_approval: { label: "Pending Approval", bg: "rgba(234,179,8,.15)",  text: "#EAB308" },
    failed:           { label: "Failed",           bg: "rgba(239,68,68,.15)",  text: "#F87171" },
    planning:         { label: "In Progress",      bg: "rgba(59,130,246,.12)", text: "#60A5FA" },
    running:          { label: "In Progress",      bg: "rgba(59,130,246,.12)", text: "#60A5FA" },
    cancelled:        { label: "Cancelled",        bg: "rgba(148,163,184,.1)", text: "#94A3B8" },
};

function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1) return "now";
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h`;
    return `${Math.floor(hours / 24)}d`;
}

interface ActionCardProps {
    run: AgentRun;
    onTrace: (id: string) => void;
    onDismiss: (id: string) => void;
}

export function ActionCard({ run, onTrace, onDismiss }: ActionCardProps) {
    const badge = BADGE[run.intent] ?? { bg: "rgba(148,163,184,.1)", text: "#94A3B8", label: run.intent };
    const barColor = STATUS_BAR[run.status] ?? "var(--muted-foreground)";
    const { summary, detail } = summarizeAction(run);
    const statusBadge = STATUS_BADGE[run.status] ?? { label: run.status, bg: "rgba(148,163,184,.1)", text: "#94A3B8" };

    return (
        <article
            style={{
                display: "flex",
                borderRadius: 8,
                overflow: "hidden",
                border: "1px solid var(--border)",
                background: "var(--card)",
            }}
        >
            {/* Status bar */}
            <div
                data-status-bar
                data-status={run.status}
                style={{ width: 3, flexShrink: 0, background: barColor }}
            />

            {/* Card body */}
            <div style={{ flex: 1, minWidth: 0, padding: "10px 12px", display: "flex", gap: 10, alignItems: "flex-start" }}>
                {/* Platform badge */}
                <span style={{
                    fontSize: 10,
                    fontWeight: 600,
                    padding: "2px 7px",
                    borderRadius: 5,
                    background: badge.bg,
                    color: badge.text,
                    flexShrink: 0,
                    marginTop: 1,
                    letterSpacing: "0.02em",
                }}>
                    {badge.label}
                </span>

                {/* Text */}
                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                        <span style={{
                            fontSize: 10,
                            fontWeight: 600,
                            padding: "1px 6px",
                            borderRadius: 4,
                            background: statusBadge.bg,
                            color: statusBadge.text,
                            letterSpacing: "0.02em",
                        }}>
                            {statusBadge.label}
                        </span>
                    </div>
                    <p style={{ fontSize: 13, fontWeight: 500, color: "var(--foreground)", lineHeight: 1.35, margin: 0 }}>
                        {summary}
                    </p>
                    <p style={{ fontSize: 11, color: "var(--muted-foreground)", marginTop: 2, lineHeight: 1.3 }}>
                        {detail}
                    </p>
                </div>

                {/* Right column: time + trace + dismiss */}
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6, flexShrink: 0 }}>
                    <button
                        aria-label="Dismiss"
                        onClick={() => onDismiss(run.id)}
                        style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            width: 18,
                            height: 18,
                            borderRadius: 4,
                            border: "none",
                            background: "none",
                            color: "var(--muted-foreground)",
                            cursor: "pointer",
                            opacity: 0.5,
                            fontSize: 14,
                            lineHeight: 1,
                            padding: 0,
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.opacity = "1"; e.currentTarget.style.color = "var(--foreground)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.opacity = "0.5"; e.currentTarget.style.color = "var(--muted-foreground)"; }}
                    >
                        ✕
                    </button>
                    <span style={{ fontSize: 10, color: "var(--muted-foreground)", opacity: 0.7 }}>
                        {relativeTime(run.created_at)}
                    </span>
                    <button
                        aria-label="View trace"
                        onClick={() => onTrace(run.id)}
                        style={{
                            fontSize: 11,
                            fontWeight: 500,
                            color: "var(--primary)",
                            background: "rgba(59,130,246,.08)",
                            border: "1px solid rgba(59,130,246,.25)",
                            borderRadius: 5,
                            cursor: "pointer",
                            padding: "3px 8px",
                            lineHeight: 1.4,
                            transition: "background 0.15s, border-color 0.15s",
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.background = "rgba(59,130,246,.16)";
                            e.currentTarget.style.borderColor = "rgba(59,130,246,.5)";
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.background = "rgba(59,130,246,.08)";
                            e.currentTarget.style.borderColor = "rgba(59,130,246,.25)";
                        }}
                    >
                        Trace →
                    </button>
                </div>
            </div>
        </article>
    );
}
