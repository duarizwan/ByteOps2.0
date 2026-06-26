"use client";

import { useState, useEffect } from "react";
import { TrendingUp, Activity, Zap, Shield, Clock, CheckCircle, XCircle, Loader2, AlertTriangle } from "lucide-react";
import { TopBar } from "@/components/dashboard/top-bar";
import { api } from "@/lib/api";

/* ── Types ────────────────────────────────────────────────────────────────── */
interface DayData { date: string; label: string; total: number; completed: number; failed: number; }
interface ToolData { tool: string; count: number; }
interface FlaggedRun { id: string; intent: string; status: string; created_at: string; anomaly_score: number | null; llm_score: number | null; }
interface AnalyticsSummary {
    total_runs: number;
    runs_last_30_days: number;
    success_rate: number;
    failure_rate: number;
    anomaly_rate: number;
    flagged_count: number;
    status_breakdown: Record<string, number>;
    runs_by_day: DayData[];
    tool_breakdown: ToolData[];
    active_workflows: number;
    hired_agents: number;
    flagged_runs: FlaggedRun[];
}

/* ── Stat Card ────────────────────────────────────────────────────────────── */
function StatCard({
    label, value, sub, icon, accent,
}: {
    label: string; value: string | number; sub?: string; icon: React.ReactNode; accent: string;
}) {
    return (
        <div className="bg-card border border-border rounded-2xl p-5 flex items-start gap-4">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${accent}`}>
                {icon}
            </div>
            <div>
                <p className="text-2xl font-bold text-foreground">{value}</p>
                <p className="text-xs font-medium text-muted-foreground">{label}</p>
                {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
            </div>
        </div>
    );
}

/* ── Bar Chart (inline SVG) ───────────────────────────────────────────────── */
function BarChart({ data }: { data: DayData[] }) {
    const max = Math.max(...data.map((d) => d.total), 1);
    const W = 100; // percentage per bar group
    const BAR_H = 120;

    return (
        <div className="bg-card border border-border rounded-2xl p-5">
            <p className="text-sm font-semibold text-foreground mb-4">Runs — Last 7 Days</p>
            <div className="flex items-end gap-2" style={{ height: BAR_H + 32 }}>
                {data.map((d) => {
                    const totalH = Math.round((d.total / max) * BAR_H);
                    const compH = Math.round((d.completed / max) * BAR_H);
                    const failH = Math.round((d.failed / max) * BAR_H);
                    return (
                        <div key={d.date} className="flex-1 flex flex-col items-center gap-1">
                            {/* Stacked bar */}
                            <div className="relative w-full flex flex-col justify-end" style={{ height: BAR_H }}>
                                {d.total > 0 ? (
                                    <>
                                        {/* pending / other */}
                                        {totalH - compH - failH > 0 && (
                                            <div
                                                className="w-full rounded-t bg-muted-foreground/20"
                                                style={{ height: totalH - compH - failH }}
                                            />
                                        )}
                                        {failH > 0 && (
                                            <div className="w-full bg-red-500/70" style={{ height: failH }} />
                                        )}
                                        {compH > 0 && (
                                            <div
                                                className={`w-full bg-blue-500 ${failH === 0 && totalH - compH - failH === 0 ? "rounded-t" : ""}`}
                                                style={{ height: compH }}
                                            />
                                        )}
                                    </>
                                ) : (
                                    <div className="w-full bg-muted/30 rounded" style={{ height: 4 }} />
                                )}
                            </div>
                            <span className="text-xs text-muted-foreground">{d.label}</span>
                            <span className="text-xs font-medium text-foreground">{d.total || ""}</span>
                        </div>
                    );
                })}
            </div>
            {/* Legend */}
            <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-blue-500 inline-block" />Completed</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-red-500/70 inline-block" />Failed</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-muted-foreground/20 inline-block" />Other</span>
            </div>
        </div>
    );
}

/* ── Tool Breakdown ───────────────────────────────────────────────────────── */
const TOOL_COLORS: Record<string, string> = {
    gmail: "bg-red-500",
    github: "bg-gray-700 dark:bg-gray-400",
    jira: "bg-blue-600",
    slack: "bg-purple-500",
    calendar: "bg-cyan-500",
    dropbox: "bg-blue-400",
};
const TOOL_LABELS: Record<string, string> = {
    gmail: "Gmail", github: "GitHub", jira: "Jira", slack: "Slack", calendar: "Calendar", dropbox: "Dropbox",
};

function ToolBreakdown({ data, total }: { data: ToolData[]; total: number }) {
    const max = Math.max(...data.map((d) => d.count), 1);
    return (
        <div className="bg-card border border-border rounded-2xl p-5">
            <p className="text-sm font-semibold text-foreground mb-4">Runs by Tool</p>
            {data.length === 0 ? (
                <p className="text-xs text-muted-foreground">No data yet.</p>
            ) : (
                <div className="space-y-3">
                    {data.map((d) => (
                        <div key={d.tool} className="flex items-center gap-3">
                            <span className="w-16 text-xs text-muted-foreground capitalize shrink-0">
                                {TOOL_LABELS[d.tool] ?? d.tool}
                            </span>
                            <div className="flex-1 bg-muted rounded-full h-2 overflow-hidden">
                                <div
                                    className={`h-full rounded-full ${TOOL_COLORS[d.tool] ?? "bg-blue-500"}`}
                                    style={{ width: `${Math.round((d.count / max) * 100)}%` }}
                                />
                            </div>
                            <span className="text-xs font-medium text-foreground w-6 text-right">{d.count}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

/* ── Flagged Runs Table ───────────────────────────────────────────────────── */
function FlaggedRunsTable({ runs }: { runs: FlaggedRun[] }) {
    function fmt(iso: string) {
        const d = new Date(iso);
        return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" }) + " " + d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
    }

    return (
        <div className="bg-card border border-border rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-4">
                <Shield className="w-4 h-4 text-amber-500" />
                <p className="text-sm font-semibold text-foreground">Recently Flagged Runs</p>
            </div>
            {runs.length === 0 ? (
                <div className="text-center py-6">
                    <CheckCircle className="w-8 h-8 text-green-500 mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">No anomalies detected — all clear.</p>
                </div>
            ) : (
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-left text-xs text-muted-foreground border-b border-border">
                                <th className="pb-2 font-medium">Tool</th>
                                <th className="pb-2 font-medium">Status</th>
                                <th className="pb-2 font-medium">Time</th>
                                <th className="pb-2 font-medium text-right">Score</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                            {runs.map((r) => (
                                <tr key={r.id} className="hover:bg-muted/30 transition-colors">
                                    <td className="py-2.5 capitalize text-foreground">{TOOL_LABELS[r.intent] ?? r.intent ?? "—"}</td>
                                    <td className="py-2.5">
                                        <span className={`text-xs px-2 py-0.5 rounded-full ${r.status === "completed" ? "bg-green-500/10 text-green-600 dark:text-green-400" : r.status === "failed" ? "bg-red-500/10 text-red-500" : "bg-muted text-muted-foreground"}`}>
                                            {r.status}
                                        </span>
                                    </td>
                                    <td className="py-2.5 text-muted-foreground text-xs">{fmt(r.created_at)}</td>
                                    <td className="py-2.5 text-right">
                                        {r.anomaly_score != null ? (
                                            <span className="text-amber-500 font-mono text-xs">{r.anomaly_score.toFixed(2)}</span>
                                        ) : r.llm_score != null ? (
                                            <span className="text-amber-500 font-mono text-xs">{r.llm_score}/10</span>
                                        ) : (
                                            <span className="text-muted-foreground text-xs">—</span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */
export default function AnalyticsPage() {
    const [data, setData] = useState<AnalyticsSummary | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        api<AnalyticsSummary>("/api/analytics/summary")
            .then(setData)
            .catch((e) => setError(e instanceof Error ? e.message : "Failed to load analytics"))
            .finally(() => setIsLoading(false));
    }, []);

    return (
        <div className="min-h-screen flex flex-col bg-background">
            <TopBar />

            <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-8 space-y-8">
                {/* Header */}
                <div>
                    <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Track agent activity, tool usage, and anomaly detection across your workspace.
                    </p>
                </div>

                {isLoading ? (
                    <div className="flex items-center justify-center py-24">
                        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                    </div>
                ) : error ? (
                    <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-500">
                        <AlertTriangle className="w-4 h-4" />
                        {error}
                    </div>
                ) : data ? (
                    <>
                        {/* KPI Cards */}
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                            <StatCard
                                label="Total Agent Runs"
                                value={data.total_runs}
                                sub={`${data.runs_last_30_days} in last 30 days`}
                                icon={<Activity className="w-5 h-5 text-blue-500" />}
                                accent="bg-blue-500/10"
                            />
                            <StatCard
                                label="Success Rate"
                                value={`${data.success_rate}%`}
                                sub={`${data.failure_rate}% failure rate`}
                                icon={<CheckCircle className="w-5 h-5 text-green-500" />}
                                accent="bg-green-500/10"
                            />
                            <StatCard
                                label="Agents Hired"
                                value={data.hired_agents}
                                sub={`${data.active_workflows} active workflows`}
                                icon={<Zap className="w-5 h-5 text-purple-500" />}
                                accent="bg-purple-500/10"
                            />
                            <StatCard
                                label="Anomaly Rate"
                                value={`${data.anomaly_rate}%`}
                                sub={`${data.flagged_count} flagged runs`}
                                icon={<Shield className="w-5 h-5 text-amber-500" />}
                                accent="bg-amber-500/10"
                            />
                        </div>

                        {/* Charts row */}
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                            <div className="lg:col-span-2">
                                <BarChart data={data.runs_by_day} />
                            </div>
                            <ToolBreakdown data={data.tool_breakdown} total={data.total_runs} />
                        </div>

                        {/* Flagged runs */}
                        <FlaggedRunsTable runs={data.flagged_runs} />

                        {/* Status breakdown */}
                        {Object.keys(data.status_breakdown).length > 0 && (
                            <div className="bg-card border border-border rounded-2xl p-5">
                                <p className="text-sm font-semibold text-foreground mb-4">All-time Status Breakdown</p>
                                <div className="flex flex-wrap gap-3">
                                    {Object.entries(data.status_breakdown).map(([status, count]) => (
                                        <div key={status} className="flex items-center gap-2 px-3 py-1.5 bg-muted rounded-lg">
                                            <span className="text-xs text-muted-foreground capitalize">{status}</span>
                                            <span className="text-sm font-bold text-foreground">{count}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                ) : null}
            </main>
        </div>
    );
}
