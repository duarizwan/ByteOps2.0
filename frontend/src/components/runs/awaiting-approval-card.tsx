"use client";

import { useState } from "react";
import Link from "next/link";
import type { AgentRun } from "@/hooks/use-agent-runs";
import { summarizeAction } from "@/lib/summarize-action";
import { api } from "@/lib/api";

const BADGE: Record<string, { bg: string; text: string; label: string }> = {
    gmail:    { bg: "rgba(239,68,68,.14)",   text: "#F87171", label: "Gmail"    },
    slack:    { bg: "rgba(168,85,247,.12)",  text: "#C084FC", label: "Slack"    },
    jira:     { bg: "rgba(59,130,246,.12)",  text: "#60A5FA", label: "Jira"     },
    github:   { bg: "rgba(107,114,128,.12)", text: "#9CA3AF", label: "GitHub"   },
    calendar: { bg: "rgba(34,197,94,.12)",   text: "#4ADE80", label: "Calendar" },
    dropbox:  { bg: "rgba(14,165,233,.12)",  text: "#38BDF8", label: "Dropbox"  },
};

interface AwaitingApprovalCardProps {
    run: AgentRun;
    onApproved: (id: string) => void;
    onCancelled: (id: string) => void;
}

export function AwaitingApprovalCard({ run, onApproved, onCancelled }: AwaitingApprovalCardProps) {
    const [approving, setApproving] = useState(false);
    const [cancelling, setCancelling] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const badge = BADGE[run.intent] ?? { bg: "rgba(148,163,184,.1)", text: "#94A3B8", label: run.intent };
    const { summary } = summarizeAction(run);

    async function handleApprove() {
        setApproving(true);
        setError(null);
        // Optimistic dismiss
        onApproved(run.id);
        try {
            await api(`/api/agent-runs/${run.id}/approve`, { method: "POST" });
        } catch (e: unknown) {
            const status = (e as { status?: number }).status;
            if (status === 409) return; // stale — already dismissed
            // Undo optimistic on real error
            setError("Could not approve — please try again.");
        } finally {
            setApproving(false);
        }
    }

    async function handleCancel() {
        setCancelling(true);
        setError(null);
        onCancelled(run.id);
        try {
            await api(`/api/agent-runs/${run.id}/reject`, { method: "POST" });
        } catch (e: unknown) {
            const status = (e as { status?: number }).status;
            if (status === 409) return;
            setError("Could not cancel — please try again.");
        } finally {
            setCancelling(false);
        }
    }

    return (
        <article style={{
            display: "flex",
            borderRadius: 8,
            overflow: "hidden",
            border: "1px solid color-mix(in srgb, #EAB308 30%, transparent)",
            background: "var(--card)",
        }}>
            {/* Amber status bar */}
            <div
                data-status-bar
                data-status={run.status}
                style={{ width: 3, flexShrink: 0, background: "#EAB308" }}
            />

            <div style={{ flex: 1, minWidth: 0, padding: "10px 12px" }}>
                {/* Top row */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <span style={{
                        fontSize: 10,
                        fontWeight: 600,
                        padding: "2px 7px",
                        borderRadius: 5,
                        background: badge.bg,
                        color: badge.text,
                        letterSpacing: "0.02em",
                    }}>
                        {badge.label}
                    </span>
                    <p style={{ flex: 1, fontSize: 13, fontWeight: 500, color: "var(--foreground)", margin: 0 }}>
                        {summary}
                    </p>
                </div>

                {error && (
                    <p style={{ fontSize: 11, color: "#EF4444", marginBottom: 6 }}>{error}</p>
                )}

                {/* Action buttons */}
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <button
                        aria-label="Approve"
                        onClick={handleApprove}
                        disabled={approving || cancelling}
                        style={{
                            padding: "4px 12px",
                            fontSize: 12,
                            fontWeight: 600,
                            borderRadius: 6,
                            border: "none",
                            background: "#22C55E",
                            color: "#fff",
                            cursor: approving ? "wait" : "pointer",
                            opacity: approving ? 0.7 : 1,
                        }}
                    >
                        {approving ? "Approving…" : "Approve"}
                    </button>
                    <Link
                        href="/dashboard"
                        style={{
                            fontSize: 12,
                            color: "var(--primary)",
                            textDecoration: "none",
                        }}
                        aria-label="Edit in chat"
                    >
                        Edit in chat →
                    </Link>
                    <button
                        aria-label="Cancel"
                        onClick={handleCancel}
                        disabled={approving || cancelling}
                        style={{
                            padding: "4px 12px",
                            fontSize: 12,
                            fontWeight: 500,
                            borderRadius: 6,
                            border: "1px solid var(--border)",
                            background: "var(--card)",
                            color: "var(--muted-foreground)",
                            cursor: cancelling ? "wait" : "pointer",
                            opacity: cancelling ? 0.7 : 1,
                        }}
                    >
                        {cancelling ? "Cancelling…" : "Cancel"}
                    </button>
                </div>
            </div>
        </article>
    );
}
