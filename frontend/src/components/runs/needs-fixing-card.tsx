"use client";

import Link from "next/link";
import type { AgentRun } from "@/hooks/use-agent-runs";
import { summarizeAction } from "@/lib/summarize-action";
import { classifyError } from "@/lib/classify-error";

const BADGE: Record<string, { bg: string; text: string; label: string }> = {
    gmail:    { bg: "rgba(239,68,68,.14)",   text: "#F87171", label: "Gmail"    },
    slack:    { bg: "rgba(168,85,247,.12)",  text: "#C084FC", label: "Slack"    },
    jira:     { bg: "rgba(59,130,246,.12)",  text: "#60A5FA", label: "Jira"     },
    github:   { bg: "rgba(107,114,128,.12)", text: "#9CA3AF", label: "GitHub"   },
    calendar: { bg: "rgba(34,197,94,.12)",   text: "#4ADE80", label: "Calendar" },
    dropbox:  { bg: "rgba(14,165,233,.12)",  text: "#38BDF8", label: "Dropbox"  },
};

function capitalize(s: string): string {
    return s.charAt(0).toUpperCase() + s.slice(1);
}

interface NeedsFixingCardProps {
    run: AgentRun;
}

export function NeedsFixingCard({ run }: NeedsFixingCardProps) {
    const badge = BADGE[run.intent] ?? { bg: "rgba(148,163,184,.1)", text: "#94A3B8", label: run.intent };
    const { summary } = summarizeAction(run);
    const errorText = run.error ? run.error.slice(0, 120) : null;
    const category = classifyError(run.error);
    const platformLabel = badge.label;

    return (
        <article style={{
            display: "flex",
            borderRadius: 8,
            overflow: "hidden",
            border: "1px solid color-mix(in srgb, var(--destructive) 25%, transparent)",
            background: "var(--card)",
        }}>
            {/* Red status bar */}
            <div
                data-status-bar
                data-status={run.status}
                style={{ width: 3, flexShrink: 0, background: "var(--destructive)" }}
            />

            <div style={{ flex: 1, minWidth: 0, padding: "10px 12px" }}>
                {/* Top row */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span style={{
                        fontSize: 10,
                        fontWeight: 600,
                        padding: "2px 7px",
                        borderRadius: 5,
                        background: badge.bg,
                        color: badge.text,
                        letterSpacing: "0.02em",
                        flexShrink: 0,
                    }}>
                        {badge.label}
                    </span>
                    <p style={{ flex: 1, fontSize: 13, fontWeight: 500, color: "var(--foreground)", margin: 0 }}>
                        {summary}
                    </p>
                </div>

                {errorText && (
                    <p style={{ fontSize: 11, color: "#EF4444", marginBottom: 6, lineHeight: 1.4 }}>
                        {errorText}
                    </p>
                )}

                {/* Fix CTA */}
                {category === "auth" && (
                    <Link
                        href="/settings"
                        style={{
                            fontSize: 12,
                            color: "var(--primary)",
                            textDecoration: "none",
                            fontWeight: 500,
                        }}
                        aria-label={`Reconnect ${platformLabel}`}
                    >
                        Reconnect {platformLabel} →
                    </Link>
                )}
                {category === "timeout" && (
                    <button
                        aria-label="Retry"
                        disabled
                        style={{
                            padding: "3px 10px",
                            fontSize: 12,
                            fontWeight: 500,
                            borderRadius: 6,
                            border: "1px solid var(--border)",
                            background: "var(--card)",
                            color: "var(--muted-foreground)",
                            cursor: "not-allowed",
                            opacity: 0.5,
                        }}
                    >
                        Retry →
                    </button>
                )}
            </div>
        </article>
    );
}
