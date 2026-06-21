"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
    Mail, Code2, Calendar, RefreshCw, Play, Pause, Zap,
    Loader2, AlertTriangle, X, CheckCircle, ArrowLeft,
} from "lucide-react";
import { TopBar } from "@/components/dashboard/top-bar";
import { useAgentDetail, AgentRun } from "@/hooks/use-agent-detail";

/* ── Icon map ──────────────────────────────────────────────────────────── */
const ICON_MAP: Record<string, React.ReactNode> = {
    mail: <Mail className="w-5 h-5" />,
    code: <Code2 className="w-5 h-5" />,
    calendar: <Calendar className="w-5 h-5" />,
    "refresh-cw": <RefreshCw className="w-5 h-5" />,
};

/* ── Helpers ───────────────────────────────────────────────────────────── */
function relativeTime(iso: string | null): string {
    if (!iso) return "Never";
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}

function nextRunTime(iso: string | null): string {
    if (!iso) return "—";
    const diff = new Date(iso).getTime() - Date.now();
    if (diff < 0) return "Soon";
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `in ${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `in ${hrs}h`;
    return `in ${Math.floor(hrs / 24)}d`;
}

/* ── Status badge ────────────────────────────────────────────────────── */
function StatusBadge({ status }: { status: string }) {
    const cfg: Record<string, { label: string; className: string }> = {
        active: { label: "Active", className: "bg-green-500/15 text-green-600 dark:text-green-400" },
        running: { label: "Running", className: "bg-blue-500/15 text-blue-600 dark:text-blue-400" },
        paused: { label: "Paused", className: "bg-amber-500/15 text-amber-600 dark:text-amber-400" },
        failed: { label: "Failed", className: "bg-red-500/15 text-red-500" },
        completed: { label: "Completed", className: "bg-green-500/15 text-green-600 dark:text-green-400" },
        waiting_approval: { label: "Awaiting", className: "bg-amber-500/15 text-amber-600 dark:text-amber-400" },
    };
    const { label, className } = cfg[status] ?? { label: status, className: "bg-muted text-muted-foreground" };
    return (
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${className}`}>{label}</span>
    );
}

/* ── Anomaly score chip ────────────────────────────────────────────── */
function AnomalyScore({ score }: { score: number | null }) {
    if (score === null) return <span className="text-xs text-muted-foreground">—</span>;
    const colour =
        score < 0.3 ? "text-green-600 dark:text-green-400"
        : score < 0.6 ? "text-amber-600 dark:text-amber-400"
        : "text-red-500";
    return <span className={`text-xs font-mono ${colour}`}>{score.toFixed(2)}</span>;
}

/* ── KPI card ────────────────────────────────────────────────────────── */
function KpiCard({ label, value, sub, warn }: { label: string; value: string; sub?: string; warn?: boolean }) {
    return (
        <div className="bg-card border border-border rounded-2xl p-4">
            <p className="text-2xl font-bold text-foreground">{value}</p>
            <p className="text-xs text-muted-foreground mt-1">{label}</p>
            {sub && (
                <p className={`text-xs mt-1 ${warn ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"}`}>
                    {sub}
                </p>
            )}
        </div>
    );
}

/* ── Run history bar chart (30 days) ──────────────────────────────────── */
function RunHistoryChart({ runs }: { runs: AgentRun[] }) {
    // Build a map of date string → { success: n, failed: n }
    const days: { label: string; success: number; failed: number }[] = [];
    const now = new Date();
    for (let i = 29; i >= 0; i--) {
        const d = new Date(now);
        d.setDate(d.getDate() - i);
        const key = d.toISOString().slice(0, 10);
        const dayRuns = runs.filter((r) => (r.created_at ?? "").startsWith(key));
        days.push({
            label: i === 0 ? "today" : key.slice(5),
            success: dayRuns.filter((r) => r.status === "completed").length,
            failed: dayRuns.filter((r) => r.status === "failed").length,
        });
    }
    const maxCount = Math.max(...days.map((d) => d.success + d.failed), 1);
    const BAR_H = 80;

    return (
        <div className="bg-card border border-border rounded-2xl p-5">
            <p className="text-sm font-semibold text-foreground mb-4">Runs — Last 30 Days</p>
            <div className="flex items-end gap-[3px]" style={{ height: BAR_H + 20 }}>
                {days.map((d, i) => {
                    const total = d.success + d.failed;
                    const h = total === 0 ? 2 : Math.max(Math.round((total / maxCount) * BAR_H), 4);
                    const colour =
                        total === 0 ? "bg-border"
                        : d.failed > 0 ? "bg-red-500"
                        : "bg-green-500";
                    return (
                        <div key={i} className="flex-1 flex flex-col items-center gap-1">
                            <div
                                className={`w-full rounded-sm ${colour} opacity-80 transition-all`}
                                style={{ height: h }}
                                title={`${d.label}: ${total} run(s)`}
                            />
                            {i === 29 && (
                                <span className="text-[9px] text-muted-foreground whitespace-nowrap">today</span>
                            )}
                        </div>
                    );
                })}
            </div>
            <div className="flex gap-4 mt-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="w-2.5 h-2.5 rounded-sm bg-green-500 inline-block" /> Success
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="w-2.5 h-2.5 rounded-sm bg-red-500 inline-block" /> Failed
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="w-2.5 h-2.5 rounded-sm bg-border inline-block" /> No run
                </div>
            </div>
        </div>
    );
}

/* ── Run history list ──────────────────────────────────────────────── */
function RunHistoryList({ runs }: { runs: AgentRun[] }) {
    const [expandedId, setExpandedId] = useState<string | null>(null);

    if (runs.length === 0) {
        return (
            <div className="bg-card border border-border rounded-2xl p-10 text-center">
                <Zap className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
                <p className="text-sm font-medium text-foreground mb-1">No runs yet</p>
                <p className="text-xs text-muted-foreground">Trigger one with Run Now above.</p>
            </div>
        );
    }

    return (
        <div className="bg-card border border-border rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                <p className="text-sm font-semibold text-foreground">Run History</p>
                <span className="text-xs text-muted-foreground">{runs.length} runs · click a row to expand</span>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-border bg-muted/30">
                            <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Time</th>
                            <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Status</th>
                            <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Intent</th>
                            <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Anomaly</th>
                            <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Summary</th>
                        </tr>
                    </thead>
                    <tbody>
                        {runs.map((run) => (
                            <React.Fragment key={run.id}>
                                <tr
                                    onClick={() => setExpandedId(expandedId === run.id ? null : run.id)}
                                    className="border-b border-border/60 hover:bg-accent/50 cursor-pointer transition-colors"
                                >
                                    <td className="px-5 py-3 text-xs text-muted-foreground whitespace-nowrap">
                                        {run.created_at ? new Date(run.created_at).toLocaleString() : "—"}
                                    </td>
                                    <td className="px-5 py-3"><StatusBadge status={run.status} /></td>
                                    <td className="px-5 py-3">
                                        <span className="text-xs px-2 py-0.5 rounded-md bg-purple-500/10 text-purple-600 dark:text-purple-400 font-medium">
                                            {run.intent}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3"><AnomalyScore score={run.anomaly_score} /></td>
                                    <td className="px-5 py-3 max-w-xs">
                                        <span className="text-xs text-muted-foreground truncate block">
                                            {run.summary ?? run.error ?? "—"}
                                        </span>
                                    </td>
                                </tr>
                                {expandedId === run.id && (
                                    <tr key={`${run.id}-exp`} className="border-b border-border bg-blue-500/5 border-l-2 border-l-blue-500">
                                        <td colSpan={5} className="px-5 py-4">
                                            <p className="text-xs text-muted-foreground mb-1 font-medium">Full response</p>
                                            <pre className="text-xs text-foreground whitespace-pre-wrap leading-relaxed">
                                                {run.summary || run.error || "No output recorded."}
                                            </pre>
                                        </td>
                                    </tr>
                                )}
                            </React.Fragment>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

/* ── Pending approvals panel ─────────────────────────────────────── */
function PendingApprovals({ runs }: { runs: AgentRun[] }) {
    const pending = runs.filter((r) => r.status === "waiting_approval");
    if (pending.length === 0) return null;

    return (
        <div className="bg-card border border-amber-500/40 rounded-2xl overflow-hidden">
            <div className="flex items-center gap-3 px-5 py-4 border-b border-amber-500/20">
                <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                <p className="text-sm font-semibold text-foreground">Pending Approvals</p>
                <span className="ml-auto text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400">
                    {pending.length} waiting
                </span>
            </div>
            {pending.map((run) => (
                <div key={run.id} className="flex items-center justify-between gap-4 px-5 py-3.5 border-b border-border/60 last:border-0">
                    <div>
                        <p className="text-sm text-foreground">{run.summary ?? "Action requires approval"}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            Requested {relativeTime(run.created_at)} · Run {run.id.slice(0, 8)}
                        </p>
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                        <button className="px-3 py-1.5 text-xs font-medium bg-green-500/15 text-green-600 dark:text-green-400 border border-green-500/25 rounded-lg hover:bg-green-500/25 transition-colors">
                            Approve
                        </button>
                        <button className="px-3 py-1.5 text-xs font-medium bg-red-500/10 text-red-500 border border-red-500/20 rounded-lg hover:bg-red-500/20 transition-colors">
                            Deny
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}

/* ── Page ───────────────────────────────────────────────────────────────── */
export default function AgentDetailPage() {
    const params = useParams();
    const id = params.id as string;
    const { agent, runs, isLoading, error, pause, resume, runNow } = useAgentDetail(id);
    const [actionError, setActionError] = useState<string | null>(null);
    const [actionLoading, setActionLoading] = useState(false);

    const handleAction = (fn: () => Promise<void>) => async () => {
        setActionLoading(true);
        setActionError(null);
        try {
            await fn();
        } catch (e) {
            setActionError(e instanceof Error ? e.message : "Action failed");
        } finally {
            setActionLoading(false);
        }
    };

    const successRate =
        agent && agent.total_runs > 0
            ? Math.round(
                  (runs.filter((r) => r.status === "completed").length / agent.total_runs) * 100
              )
            : null;

    if (isLoading) {
        return (
            <div className="min-h-screen flex flex-col bg-background">
                <TopBar />
                <div className="flex-1 flex items-center justify-center">
                    <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
            </div>
        );
    }

    if (error || !agent) {
        return (
            <div className="min-h-screen flex flex-col bg-background">
                <TopBar />
                <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-4">
                    <p className="text-muted-foreground text-sm">{error ?? "Agent not found."}</p>
                    <Link href="/agents" className="text-sm text-blue-500 hover:underline">
                        ← Back to Agents
                    </Link>
                </div>
            </div>
        );
    }

    const icon = ICON_MAP[agent.template?.icon ?? ""] ?? <Zap className="w-5 h-5" />;
    const color = agent.template?.color ?? "#6b7280";

    return (
        <div className="min-h-screen flex flex-col bg-background">
            <TopBar />
            <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-8 space-y-6">

                {/* Breadcrumb */}
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Link href="/agents" className="flex items-center gap-1 text-blue-500 hover:underline">
                        <ArrowLeft className="w-3.5 h-3.5" /> Agents
                    </Link>
                    <span>/</span>
                    <span className="text-foreground">{agent.name}</span>
                </div>

                {/* Action error */}
                {actionError && (
                    <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-500">
                        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                        {actionError}
                        <button onClick={() => setActionError(null)} className="ml-auto">
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                )}

                {/* Page header */}
                <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-4">
                        <div
                            className="w-12 h-12 rounded-2xl flex items-center justify-center text-white flex-shrink-0"
                            style={{ background: color }}
                        >
                            {icon}
                        </div>
                        <div>
                            <div className="flex items-center gap-2">
                                <h1 className="text-xl font-bold text-foreground">{agent.name}</h1>
                                <StatusBadge status={agent.status} />
                            </div>
                            <p className="text-sm text-muted-foreground mt-0.5">
                                {agent.template?.name} · {agent.schedule || "—"}
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                        <button
                            onClick={handleAction(runNow)}
                            disabled={actionLoading || agent.status === "running"}
                            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
                        >
                            {actionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                            Run Now
                        </button>
                        {agent.status === "paused" ? (
                            <button
                                onClick={handleAction(resume)}
                                disabled={actionLoading}
                                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium border border-border hover:bg-accent text-foreground rounded-lg transition-colors disabled:opacity-50"
                            >
                                <CheckCircle className="w-3.5 h-3.5" /> Resume
                            </button>
                        ) : (
                            <button
                                onClick={handleAction(pause)}
                                disabled={actionLoading || agent.status === "running"}
                                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium border border-border hover:bg-accent text-foreground rounded-lg transition-colors disabled:opacity-50"
                            >
                                <Pause className="w-3.5 h-3.5" /> Pause
                            </button>
                        )}
                    </div>
                </div>

                {/* KPI row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <KpiCard label="Total Runs" value={String(agent.total_runs)} />
                    <KpiCard
                        label="Success Rate"
                        value={successRate !== null ? `${successRate}%` : "—"}
                        sub={successRate !== null ? `${runs.filter(r => r.status === "completed").length} / ${agent.total_runs} completed` : undefined}
                    />
                    <KpiCard
                        label="Last Run"
                        value={relativeTime(agent.last_run_at)}
                    />
                    <KpiCard
                        label="Next Run"
                        value={nextRunTime(agent.next_run_at)}
                        warn={!!agent.last_error}
                        sub={agent.last_error ? "⚠ Error on last run" : undefined}
                    />
                </div>

                {/* Pending approvals */}
                <PendingApprovals runs={runs} />

                {/* Run history chart */}
                <RunHistoryChart runs={runs} />

                {/* Run history list */}
                <RunHistoryList runs={runs} />

            </main>
        </div>
    );
}
