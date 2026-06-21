"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
    Mail, Code2, Calendar, RefreshCw, Play, Pause, Trash2,
    Plus, CheckCircle, XCircle, Clock, Zap, ChevronRight,
    Loader2, AlertTriangle, X, Settings
} from "lucide-react";
import { TopBar } from "@/components/dashboard/top-bar";
import { useAgents, AgentTemplate, HiredAgent } from "@/hooks/use-agents";

/* ── Icon map ──────────────────────────────────────────────────────────────── */
const ICON_MAP: Record<string, React.ReactNode> = {
    mail: <Mail className="w-5 h-5" />,
    code: <Code2 className="w-5 h-5" />,
    calendar: <Calendar className="w-5 h-5" />,
    "refresh-cw": <RefreshCw className="w-5 h-5" />,
};

const TOOL_LABELS: Record<string, string> = {
    gmail: "Gmail",
    slack: "Slack",
    github: "GitHub",
    jira: "Jira",
    calendar: "Calendar",
    dropbox: "Dropbox",
};

/* ── Status badge ─────────────────────────────────────────────────────────── */
function StatusBadge({ status }: { status: string }) {
    const cfg: Record<string, { label: string; className: string }> = {
        active: { label: "Active", className: "bg-green-500/15 text-green-600 dark:text-green-400" },
        running: { label: "Running", className: "bg-blue-500/15 text-blue-600 dark:text-blue-400" },
        paused: { label: "Paused", className: "bg-amber-500/15 text-amber-600 dark:text-amber-400" },
        failed: { label: "Failed", className: "bg-red-500/15 text-red-500" },
    };
    const { label, className } = cfg[status] ?? { label: status, className: "bg-muted text-muted-foreground" };
    return (
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${className}`}>{label}</span>
    );
}

/* ── Relative time helper ─────────────────────────────────────────────────── */
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

/* ── Hire Modal ───────────────────────────────────────────────────────────── */
function HireModal({
    template,
    onClose,
    onHire,
}: {
    template: AgentTemplate;
    onClose: () => void;
    onHire: (name: string, config: Record<string, unknown>, schedule: string) => Promise<void>;
}) {
    const [name, setName] = useState(template.name);
    const [schedule, setSchedule] = useState(template.default_schedule);
    const [config, setConfig] = useState<Record<string, unknown>>(
        Object.fromEntries(template.config_schema.map((f) => [f.key, f.default]))
    );
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async () => {
        setIsLoading(true);
        setError(null);
        try {
            await onHire(name.trim() || template.name, config, schedule);
            onClose();
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to hire agent");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <div className="bg-card border border-border rounded-2xl w-full max-w-lg shadow-2xl">
                {/* Header */}
                <div className="flex items-center justify-between p-5 border-b border-border">
                    <div className="flex items-center gap-3">
                        <div
                            className="w-9 h-9 rounded-xl flex items-center justify-center text-white"
                            style={{ background: template.color }}
                        >
                            {ICON_MAP[template.icon] ?? <Zap className="w-5 h-5" />}
                        </div>
                        <div>
                            <p className="font-semibold text-foreground">Hire {template.name}</p>
                            <p className="text-xs text-muted-foreground">Configure your agent</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-accent">
                        <X className="w-4 h-4 text-muted-foreground" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-5 space-y-4 max-h-[60vh] overflow-y-auto">
                    {/* Name */}
                    <div>
                        <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Agent Name</label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 text-foreground"
                        />
                    </div>

                    {/* Schedule */}
                    <div>
                        <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Run Schedule</label>
                        <select
                            value={schedule}
                            onChange={(e) => setSchedule(e.target.value)}
                            className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 text-foreground"
                        >
                            {template.schedule_options.map((opt) => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                        </select>
                    </div>

                    {/* Config fields */}
                    {template.config_schema.length > 0 && (
                        <div className="space-y-3">
                            <p className="text-xs font-medium text-muted-foreground">Configuration</p>
                            {template.config_schema.map((field) => (
                                <div key={field.key} className="flex items-center justify-between gap-4">
                                    <label className="text-sm text-foreground flex-1">{field.label}</label>
                                    {field.type === "boolean" ? (
                                        <button
                                            type="button"
                                            onClick={() => setConfig((c) => ({ ...c, [field.key]: !c[field.key] }))}
                                            className={`relative w-9 h-5 rounded-full transition-colors ${config[field.key] ? "bg-blue-500" : "bg-muted-foreground/30"}`}
                                        >
                                            <span
                                                className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${config[field.key] ? "translate-x-[18px]" : "translate-x-0.5"}`}
                                            />
                                        </button>
                                    ) : field.type === "number" ? (
                                        <input
                                            type="number"
                                            value={config[field.key] as number}
                                            onChange={(e) => setConfig((c) => ({ ...c, [field.key]: Number(e.target.value) }))}
                                            className="w-20 px-2 py-1 text-sm bg-background border border-border rounded-lg text-right text-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                                        />
                                    ) : (
                                        <input
                                            type="text"
                                            value={config[field.key] as string}
                                            onChange={(e) => setConfig((c) => ({ ...c, [field.key]: e.target.value }))}
                                            placeholder={`e.g. ${field.default || ""}`}
                                            className="w-32 px-2 py-1 text-sm bg-background border border-border rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                                        />
                                    )}
                                </div>
                            ))}
                        </div>
                    )}

                    {error && (
                        <div className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-500">
                            <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                            {error}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-2 p-4 border-t border-border">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSubmit}
                        disabled={isLoading}
                        className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
                    >
                        {isLoading && <Loader2 className="w-3 h-3 animate-spin" />}
                        Hire Agent
                    </button>
                </div>
            </div>
        </div>
    );
}

/* ── Hired Agent Card ──────────────────────────────────────────────────────── */
function HiredAgentCard({
    agent,
    onPause,
    onResume,
    onRun,
    onFire,
}: {
    agent: HiredAgent;
    onPause: () => void;
    onResume: () => void;
    onRun: () => void;
    onFire: () => void;
}) {
    const [confirmFire, setConfirmFire] = useState(false);
    const icon = ICON_MAP[agent.template?.icon ?? ""] ?? <Zap className="w-5 h-5" />;
    const color = agent.template?.color ?? "#6b7280";

    return (
        <div className="bg-card border border-border rounded-2xl p-5 flex flex-col gap-4 hover:shadow-md transition-shadow">
            {/* Header */}
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                    <div
                        className="w-10 h-10 rounded-xl flex items-center justify-center text-white flex-shrink-0"
                        style={{ background: color }}
                    >
                        {icon}
                    </div>
                    <div>
                        <p className="font-semibold text-foreground text-sm">{agent.name}</p>
                        <p className="text-xs text-muted-foreground">{agent.template?.name}</p>
                    </div>
                </div>
                <StatusBadge status={agent.status} />
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-2 text-center">
                <div className="bg-muted/50 rounded-lg p-2">
                    <p className="text-lg font-bold text-foreground">{agent.total_runs}</p>
                    <p className="text-xs text-muted-foreground">Total Runs</p>
                </div>
                <div className="bg-muted/50 rounded-lg p-2">
                    <p className="text-sm font-semibold text-foreground">{relativeTime(agent.last_run_at)}</p>
                    <p className="text-xs text-muted-foreground">Last Run</p>
                </div>
                <div className="bg-muted/50 rounded-lg p-2">
                    <p className="text-sm font-semibold text-foreground">{nextRunTime(agent.next_run_at)}</p>
                    <p className="text-xs text-muted-foreground">Next Run</p>
                </div>
            </div>

            {/* Error */}
            {agent.last_error && (
                <div className="flex items-start gap-2 text-xs text-red-500 bg-red-500/10 rounded-lg p-2.5">
                    <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                    <span className="line-clamp-2">{agent.last_error}</span>
                </div>
            )}

            {/* Actions */}
            <div className="flex items-center gap-2 pt-1 border-t border-border">
                <button
                    onClick={onRun}
                    disabled={agent.status === "running"}
                    title="Run now"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-40"
                >
                    {agent.status === "running" ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                        <Play className="w-3 h-3" />
                    )}
                    Run
                </button>

                {agent.status === "paused" ? (
                    <button
                        onClick={onResume}
                        title="Resume"
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-border hover:bg-accent rounded-lg transition-colors text-foreground"
                    >
                        <CheckCircle className="w-3 h-3" />
                        Resume
                    </button>
                ) : (
                    <button
                        onClick={onPause}
                        disabled={agent.status === "running"}
                        title="Pause"
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-border hover:bg-accent rounded-lg transition-colors text-foreground disabled:opacity-40"
                    >
                        <Pause className="w-3 h-3" />
                        Pause
                    </button>
                )}

                <Link
                    href={`/agents/${agent.id}`}
                    className="text-xs text-blue-500 hover:underline flex items-center gap-1"
                >
                    View details →
                </Link>

                <div className="flex-1" />

                {confirmFire ? (
                    <div className="flex items-center gap-1.5">
                        <span className="text-xs text-muted-foreground">Fire agent?</span>
                        <button
                            onClick={onFire}
                            className="px-2 py-1 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700"
                        >
                            Yes
                        </button>
                        <button
                            onClick={() => setConfirmFire(false)}
                            className="px-2 py-1 text-xs border border-border rounded-lg hover:bg-accent text-foreground"
                        >
                            No
                        </button>
                    </div>
                ) : (
                    <button
                        onClick={() => setConfirmFire(true)}
                        title="Fire agent"
                        className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-red-500/10 hover:text-red-500 text-muted-foreground transition-colors"
                    >
                        <Trash2 className="w-3.5 h-3.5" />
                    </button>
                )}
            </div>
        </div>
    );
}

/* ── Template Card ────────────────────────────────────────────────────────── */
function TemplateCard({
    template,
    onHire,
}: {
    template: AgentTemplate;
    onHire: (t: AgentTemplate) => void;
}) {
    const icon = ICON_MAP[template.icon] ?? <Zap className="w-5 h-5" />;

    return (
        <div className="bg-card border border-border rounded-2xl p-5 flex flex-col gap-4 hover:shadow-md transition-shadow">
            {/* Header */}
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                    <div
                        className="w-10 h-10 rounded-xl flex items-center justify-center text-white flex-shrink-0"
                        style={{ background: template.color }}
                    >
                        {icon}
                    </div>
                    <div>
                        <p className="font-semibold text-foreground text-sm">{template.name}</p>
                        <div className="flex items-center gap-1 mt-0.5">
                            {template.available ? (
                                <><CheckCircle className="w-3 h-3 text-green-500" /><span className="text-xs text-green-600 dark:text-green-400">Ready to hire</span></>
                            ) : (
                                <><XCircle className="w-3 h-3 text-muted-foreground" /><span className="text-xs text-muted-foreground">Needs {template.required_tools.map(t => TOOL_LABELS[t] ?? t).join(", ")}</span></>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Description */}
            <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">{template.description}</p>

            {/* Capabilities */}
            <ul className="space-y-1.5">
                {template.capabilities.slice(0, 3).map((cap) => (
                    <li key={cap} className="flex items-start gap-2 text-xs text-foreground">
                        <ChevronRight className="w-3 h-3 mt-0.5 text-muted-foreground flex-shrink-0" />
                        {cap}
                    </li>
                ))}
            </ul>

            {/* Required tools */}
            <div className="flex flex-wrap gap-1.5">
                {template.required_tools.map((t) => (
                    <span key={t} className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                        {TOOL_LABELS[t] ?? t}
                    </span>
                ))}
                {template.optional_tools.map((t) => (
                    <span key={t} className="text-xs px-2 py-0.5 rounded-full border border-dashed border-border text-muted-foreground">
                        {TOOL_LABELS[t] ?? t} (optional)
                    </span>
                ))}
            </div>

            {/* CTA */}
            <div className="pt-1 border-t border-border">
                {template.available ? (
                    <button
                        onClick={() => onHire(template)}
                        className="w-full py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
                    >
                        <Plus className="w-4 h-4" />
                        Hire Agent
                    </button>
                ) : (
                    <Link
                        href="/settings"
                        className="w-full py-2 text-sm font-medium border border-border hover:bg-accent rounded-lg transition-colors flex items-center justify-center gap-2 text-muted-foreground"
                    >
                        <Settings className="w-4 h-4" />
                        Connect Tools
                    </Link>
                )}
            </div>
        </div>
    );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */
export default function AgentsPage() {
    const { templates, agents, isLoading, error, hire, pause, resume, runNow, fire } = useAgents();
    const [hiringTemplate, setHiringTemplate] = useState<AgentTemplate | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);

    const withErrorHandling = (fn: () => Promise<void>) => async () => {
        try {
            setActionError(null);
            await fn();
        } catch (e) {
            setActionError(e instanceof Error ? e.message : "Action failed");
        }
    };

    return (
        <div className="min-h-screen flex flex-col bg-background">
            <TopBar />

            <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-8 space-y-10">
                {/* Page header */}
                <div>
                    <h1 className="text-2xl font-bold text-foreground">AI Agents</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Hire autonomous agents that work for you on a schedule — no babysitting required.
                    </p>
                </div>

                {actionError && (
                    <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-500">
                        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                        {actionError}
                        <button onClick={() => setActionError(null)} className="ml-auto"><X className="w-4 h-4" /></button>
                    </div>
                )}

                {isLoading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                    </div>
                ) : error ? (
                    <div className="text-center py-20 text-muted-foreground text-sm">{error}</div>
                ) : (
                    <>
                        {/* Hired Agents */}
                        <section>
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-lg font-semibold text-foreground">
                                    Your Agents
                                    {agents.length > 0 && (
                                        <span className="ml-2 text-sm font-normal text-muted-foreground">({agents.length})</span>
                                    )}
                                </h2>
                            </div>

                            {agents.length === 0 ? (
                                <div className="border border-dashed border-border rounded-2xl p-10 text-center">
                                    <Zap className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
                                    <p className="text-sm font-medium text-foreground mb-1">No agents hired yet</p>
                                    <p className="text-xs text-muted-foreground">Hire an agent from the templates below to get started.</p>
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {agents.map((agent) => (
                                        <HiredAgentCard
                                            key={agent.id}
                                            agent={agent}
                                            onPause={withErrorHandling(() => pause(agent.id))}
                                            onResume={withErrorHandling(() => resume(agent.id))}
                                            onRun={withErrorHandling(() => runNow(agent.id))}
                                            onFire={withErrorHandling(() => fire(agent.id))}
                                        />
                                    ))}
                                </div>
                            )}
                        </section>

                        {/* Templates */}
                        <section>
                            <div className="mb-4">
                                <h2 className="text-lg font-semibold text-foreground">Agent Templates</h2>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    Each agent runs autonomously on a schedule using your connected tools.
                                </p>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
                                {templates.map((tmpl) => (
                                    <TemplateCard
                                        key={tmpl.key}
                                        template={tmpl}
                                        onHire={setHiringTemplate}
                                    />
                                ))}
                            </div>
                        </section>
                    </>
                )}
            </main>

            {hiringTemplate && (
                <HireModal
                    template={hiringTemplate}
                    onClose={() => setHiringTemplate(null)}
                    onHire={(name, config, schedule) => hire(hiringTemplate.key, name, config, schedule)}
                />
            )}
        </div>
    );
}
