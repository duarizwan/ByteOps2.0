"use client";

import type { AgentRun } from "@/hooks/use-agent-runs";

const STATUS_COLOR: Record<AgentRun["status"], string> = {
    completed:        "#22C55E",
    failed:           "#EF4444",
    waiting_approval: "#EAB308",
    planning:         "#3B82F6",
    running:          "#3B82F6",
    cancelled:        "#475569",
};

const INTENT_BADGE: Record<string, { bg: string; text: string; label: string }> = {
    gmail:    { bg: "rgba(239,68,68,.14)",   text: "#F87171", label: "Gmail"   },
    calendar: { bg: "rgba(59,130,246,.12)",  text: "#60A5FA", label: "Cal"     },
    github:   { bg: "rgba(107,114,128,.12)", text: "#9CA3AF", label: "GitHub"  },
    slack:    { bg: "rgba(168,85,247,.12)",  text: "#C084FC", label: "Slack"   },
    jira:     { bg: "rgba(59,130,246,.12)",  text: "#60A5FA", label: "Jira"    },
    dropbox:  { bg: "rgba(14,165,233,.12)",  text: "#38BDF8", label: "Dropbox" },
    workflow: { bg: "rgba(192,132,252,.12)", text: "#C084FC", label: "Flow"    },
    general:  { bg: "rgba(148,163,184,.1)",  text: "#94A3B8", label: "Gen"     },
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

function getRunTitle(run: AgentRun): string {
    const routeStep = run.steps.find((s) => s.step_type === "route");
    const msg = routeStep?.input?.message as string | undefined;
    if (msg?.trim()) return msg.length > 52 ? msg.slice(0, 50) + "…" : msg;
    const badge = INTENT_BADGE[run.intent];
    return badge ? badge.label : run.intent;
}

function getStats(run: AgentRun): string {
    const toolCount = run.steps.filter((s) => s.step_type === "tool_call").length;
    if (run.status === "waiting_approval") return "⏳ needs approval";
    if (run.status === "running" || run.status === "planning") return "running…";
    if (run.status === "failed") return "✗ failed";
    if (run.completed_at && run.created_at) {
        const durationS = (
            (new Date(run.completed_at).getTime() - new Date(run.created_at).getTime()) / 1000
        ).toFixed(1);
        return `${durationS}s · ${toolCount} tool${toolCount !== 1 ? "s" : ""}`;
    }
    return `${toolCount} tool${toolCount !== 1 ? "s" : ""}`;
}

interface RunRowProps {
    run: AgentRun;
    isSelected: boolean;
    onSelect: () => void;
    onDismiss: () => void;
}

export function RunRow({ run, isSelected, onSelect, onDismiss }: RunRowProps) {
    const barColor = STATUS_COLOR[run.status] ?? "#475569";
    const badge = INTENT_BADGE[run.intent] ?? INTENT_BADGE.general;

    return (
        <div
            onClick={onSelect}
            className="group relative flex cursor-pointer overflow-hidden rounded-lg"
            style={{
                background: isSelected
                    ? "color-mix(in srgb, var(--primary) 8%, transparent)"
                    : "transparent",
                border: `1px solid ${isSelected
                    ? "color-mix(in srgb, var(--primary) 25%, transparent)"
                    : "transparent"}`,
                transition: "background 0.12s, border-color 0.12s",
            }}
            onMouseEnter={(e) => {
                if (!isSelected) {
                    e.currentTarget.style.background = "var(--accent)";
                    e.currentTarget.style.borderColor = "var(--border)";
                }
            }}
            onMouseLeave={(e) => {
                if (!isSelected) {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.borderColor = "transparent";
                }
            }}
        >
            {/* Status bar */}
            <div style={{ width: 3, flexShrink: 0, background: barColor, alignSelf: "stretch" }} />

            {/* Row content */}
            <div style={{
                flex: 1,
                minWidth: 0,
                padding: "7px 9px",
                display: "flex",
                alignItems: "center",
                gap: 8,
            }}>
                {/* Platform badge */}
                <span style={{
                    fontSize: 9.5,
                    fontWeight: 600,
                    padding: "2px 6px",
                    borderRadius: 5,
                    background: badge.bg,
                    color: badge.text,
                    flexShrink: 0,
                    letterSpacing: "0.02em",
                }}>
                    {badge.label}
                </span>

                {/* Title + stats */}
                <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{
                        fontSize: 12,
                        fontWeight: isSelected ? 500 : 400,
                        color: "var(--foreground)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        lineHeight: 1.3,
                    }}>
                        {getRunTitle(run)}
                    </p>
                    <p style={{ fontSize: 10, color: "var(--muted-foreground)", marginTop: 2 }}>
                        {getStats(run)}
                    </p>
                </div>

                {/* Time + dismiss */}
                <div style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-end",
                    flexShrink: 0,
                    gap: 3,
                }}>
                    <span style={{ fontSize: 9.5, color: "var(--muted-foreground)", opacity: 0.6 }}>
                        {relativeTime(run.created_at)}
                    </span>
                    <button
                        onClick={(e) => { e.stopPropagation(); onDismiss(); }}
                        aria-label="Dismiss"
                        className="opacity-0 group-hover:opacity-100"
                        style={{
                            width: 14,
                            height: 14,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            background: "none",
                            border: "none",
                            cursor: "pointer",
                            fontSize: 13,
                            color: "var(--muted-foreground)",
                            lineHeight: 1,
                            padding: 0,
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = "#EF4444")}
                        onMouseLeave={(e) => (e.currentTarget.style.color = "var(--muted-foreground)")}
                    >
                        ×
                    </button>
                </div>
            </div>
        </div>
    );
}
