"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import {
    Bell,
    Workflow,
    ListChecks,
    Clock,
    ChevronLeft,
    ChevronRight,
    X,
    CheckCheck,
    Loader2,
    MessageCircle,
    RefreshCw,
    CheckCircle2,
    AlertCircle,
    Timer,
    Pause,
    Play,
    RotateCw,
} from "lucide-react";
import { getBrandIconUrl } from "@/lib/brand-icons";
import { cn } from "@/lib/utils";
import { useNotifications, Notification } from "@/hooks/use-notifications";
import { useWorkflows, WorkflowItem } from "@/hooks/use-workflows";

/* ========================
   Sync status types + hook
   ======================== */

interface ToolSyncStatus {
    tool: string;
    is_syncing: boolean;
    last_synced_at: string | null;
    next_sync_at: string | null;
    status: "syncing" | "ok" | "never" | "expired";
}

interface SyncStatus {
    tools: ToolSyncStatus[];
    sync_interval_minutes: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function useSyncStatus() {
    // Use the proper Clerk React hook — avoids the window.Clerk.session race
    // condition that sends stale/missing tokens on first render.
    const { getToken } = useAuth();
    const [status, setStatus] = useState<SyncStatus | null>(null);
    const [now, setNow] = useState(() => Date.now());

    const syncAuthFetch = useCallback(async (path: string): Promise<Response> => {
        const token = await getToken();
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = `Bearer ${token}`;
        return fetch(`${API_BASE}${path}`, { headers });
    }, [getToken]);

    const fetchStatus = useCallback(async () => {
        try {
            const res = await syncAuthFetch("/api/sync/status");
            if (res.ok) setStatus(await res.json());
        } catch { /* silent */ }
    }, [syncAuthFetch]);

    useEffect(() => {
        const initialFetchId = setTimeout(fetchStatus, 0);
        // Poll status every 30s
        const pollId = setInterval(fetchStatus, 30_000);
        // Tick the countdown every 10s for smooth updates
        const tickId = setInterval(() => setNow(Date.now()), 10_000);
        return () => {
            clearTimeout(initialFetchId);
            clearInterval(pollId);
            clearInterval(tickId);
        };
    }, [fetchStatus]);

    const triggerSync = useCallback(async () => {
        try {
            await syncAuthFetch("/api/sync/trigger");
            // Re-fetch status after short delay so spinner shows
            setTimeout(fetchStatus, 800);
        } catch { /* silent */ }
    }, [syncAuthFetch, fetchStatus]);

    return { status, now, triggerSync, refetch: fetchStatus };
}

/* ========================
   Sync Status Bar
   ======================== */

function formatCountdown(targetIso: string, now: number): string {
    const diff = new Date(targetIso).getTime() - now;
    if (diff <= 0) return "soon";
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return "< 1 min";
    if (mins === 1) return "1 min";
    return `${mins} min`;
}

function SyncStatusBar({ onSyncDone }: { onSyncDone: () => void }) {
    const { status, now, triggerSync } = useSyncStatus();

    if (!status || status.tools.length === 0) return null;

    // Aggregate across all tools (show worst-case status)
    const anySyncing = status.tools.some((t) => t.is_syncing);
    const anyExpired = status.tools.some((t) => t.status === "expired");
    const lastSyncedAt = status.tools
        .map((t) => t.last_synced_at)
        .filter(Boolean)
        .sort()
        .at(-1) ?? null; // Most recent
    const nextSyncAt = status.tools
        .map((t) => t.next_sync_at)
        .filter(Boolean)
        .sort()
        .at(0) ?? null; // Soonest

    const handleSync = async () => {
        await triggerSync();
        setTimeout(onSyncDone, 3000); // Refresh notifications after sync completes
    };

    return (
        <div className={cn(
            "flex items-center justify-between gap-2 px-3 py-2 rounded-xl text-xs border",
            anySyncing
                ? "bg-primary/5 border-primary/20 text-primary"
                : anyExpired
                    ? "bg-destructive/5 border-destructive/20 text-destructive"
                    : "bg-accent/60 border-border text-muted-foreground"
        )}>
            {/* Left — status icon + text */}
            <div className="flex items-center gap-1.5 min-w-0">
                {anySyncing ? (
                    <>
                        <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />
                        <span className="truncate">Syncing…</span>
                    </>
                ) : anyExpired ? (
                    <>
                        <AlertCircle className="w-3 h-3 flex-shrink-0" />
                        <span className="truncate">Token expired — reconnect</span>
                    </>
                ) : lastSyncedAt ? (
                    <>
                        <CheckCircle2 className="w-3 h-3 flex-shrink-0 text-emerald-500" />
                        <span className="truncate">Synced {relativeTime(lastSyncedAt)}</span>
                    </>
                ) : (
                    <>
                        <Timer className="w-3 h-3 flex-shrink-0" />
                        <span className="truncate">No sync yet</span>
                    </>
                )}
            </div>

            {/* Right — next sync countdown + manual trigger */}
            <div className="flex items-center gap-2 flex-shrink-0">
                {nextSyncAt && !anySyncing && (
                    <span className="opacity-60">
                        Next in {formatCountdown(nextSyncAt, now)}
                    </span>
                )}
                <button
                    onClick={handleSync}
                    disabled={anySyncing}
                    title="Sync now"
                    className="w-5 h-5 rounded flex items-center justify-center hover:bg-accent transition-colors disabled:opacity-40"
                >
                    <RefreshCw className={cn("w-3 h-3", anySyncing && "animate-spin")} />
                </button>
            </div>
        </div>
    );
}

/* ========================
   Helpers
   ======================== */

function relativeTime(isoString: string): string {
    const now = Date.now();
    const ms = now - new Date(isoString).getTime();
    const mins = Math.floor(ms / 60_000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days === 1) return "Yesterday";
    return `${days}d ago`;
}

function ToolIcon({ tool, className }: { tool: string; className?: string }) {
    const url = getBrandIconUrl(tool.toLowerCase());
    if (url) {
        return (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={url} alt={tool} className={cn("w-4 h-4 object-contain", className)} />
        );
    }
    return <Bell className={cn("w-4 h-4", className)} />;
}

function priorityStyles(p: string) {
    switch (p) {
        case "urgent":
        case "high":
            return "bg-destructive/10 text-destructive border border-destructive/20";
        case "medium":
            return "bg-warning/10 text-warning border border-warning/20";
        default:
            return "bg-muted text-muted-foreground";
    }
}

function PriorityBadge({ priority }: { priority: string }) {
    return (
        <span className={cn("text-xs px-2 py-0.5 rounded-full capitalize", priorityStyles(priority))}>
            {priority}
        </span>
    );
}

function statusStyles(status: WorkflowItem["status"]) {
    switch (status) {
        case "active":
            return "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20";
        case "running":
            return "bg-primary/10 text-primary border border-primary/20";
        case "failed":
            return "bg-destructive/10 text-destructive border border-destructive/20";
        case "paused":
        default:
            return "bg-muted text-muted-foreground border border-border";
    }
}

function statusLabel(status: WorkflowItem["status"]): string {
    return status.charAt(0).toUpperCase() + status.slice(1);
}

/* ========================
   Skeleton loader
   ======================== */
function NotificationSkeleton() {
    return (
        <div className="space-y-3">
            {[1, 2, 3].map((i) => (
                <div
                    key={i}
                    className="bg-card border border-border rounded-xl p-4 animate-pulse space-y-2"
                >
                    <div className="flex gap-2">
                        <div className="w-7 h-7 bg-accent rounded-lg" />
                        <div className="h-4 bg-accent rounded w-16" />
                    </div>
                    <div className="h-3 bg-accent rounded w-3/4" />
                    <div className="h-3 bg-accent rounded w-1/2" />
                </div>
            ))}
        </div>
    );
}

function WorkflowCard({
    workflow,
    onPause,
    onResume,
    onRunNow,
}: {
    workflow: WorkflowItem;
    onPause: () => void;
    onResume: () => void;
    onRunNow: () => void;
}) {
    const title = cleanActivityText(workflow.name);
    const description = workflow.description ? cleanActivityText(workflow.description) : null;
    const triggerLabel = cleanActivityText(workflow.trigger_label);
    const actionSummary = cleanActivityText(workflow.action_summary);
    const lastError = workflow.last_error ? cleanActivityText(workflow.last_error) : null;

    return (
        <div className="relative bg-card border border-border rounded-xl p-3 group transition-all">
            <div className="flex items-start justify-between gap-3 mb-2">
                <div className="min-w-0">
                    <h4 className="text-sm font-medium leading-snug">{title}</h4>
                    {description && (
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{description}</p>
                    )}
                </div>
                <span className={cn("text-xs px-2 py-0.5 rounded-full flex-shrink-0", statusStyles(workflow.status))}>
                    {statusLabel(workflow.status)}
                </span>
            </div>

            <div className="space-y-1.5 text-xs text-muted-foreground">
                <div>
                    <span className="text-foreground">Trigger: </span>
                    <span>{triggerLabel}</span>
                </div>
                <div>
                    <span className="text-foreground">Actions: </span>
                    <span>{actionSummary}</span>
                </div>
                {workflow.last_run_at && (
                    <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>Last run {relativeTime(workflow.last_run_at)}</span>
                    </div>
                )}
                {workflow.next_run_at && workflow.status !== "paused" && (
                    <div className="flex items-center gap-1">
                        <Timer className="w-3 h-3" />
                        <span>Next run {relativeTime(workflow.next_run_at)}</span>
                    </div>
                )}
                {lastError && <p className="text-destructive">{lastError}</p>}
            </div>

            <div className="flex items-center gap-1.5 mt-3">
                {workflow.status === "paused" ? (
                    <button
                        onClick={onResume}
                        className="h-7 px-2 rounded-lg flex items-center gap-1 text-xs bg-accent hover:bg-accent/80 text-foreground transition-colors"
                    >
                        <Play className="w-3 h-3" />
                        Resume
                    </button>
                ) : (
                    <button
                        onClick={onPause}
                        className="h-7 px-2 rounded-lg flex items-center gap-1 text-xs bg-accent hover:bg-accent/80 text-foreground transition-colors"
                    >
                        <Pause className="w-3 h-3" />
                        Pause
                    </button>
                )}
                <button
                    onClick={onRunNow}
                    disabled={workflow.status === "paused" || workflow.status === "running"}
                    className="h-7 px-2 rounded-lg flex items-center gap-1 text-xs bg-primary/10 hover:bg-primary/15 text-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                    <RotateCw className={cn("w-3 h-3", workflow.status === "running" && "animate-spin")} />
                    Run now
                </button>
            </div>
        </div>
    );
}

/* ========================
   Notification card
   ======================== */
function NotificationCard({
    n,
    onMarkRead,
    onDismiss,
    onSendToAI,
}: {
    n: Notification;
    onMarkRead: () => void;
    onDismiss: () => void;
    onSendToAI: (n: Notification) => void;
}) {
    const displayTitle = getNotificationTitle(n);
    const displayPriority = getNotificationPriority(n);
    const displayContent = n.content ? cleanActivityText(n.content) : null;

    return (
        <div
            className={cn(
                "relative bg-card border rounded-xl p-3 group transition-all",
                n.is_read
                    ? "border-border opacity-70"
                    : "border-primary/20 shadow-soft"
            )}
        >
            {/* Unread dot */}
            {!n.is_read && (
                <span className="absolute top-3 right-10 w-2 h-2 rounded-full bg-primary" />
            )}

            {/* Action buttons — dismiss + Ask AI */}
            <div className="absolute top-2.5 right-2.5 flex gap-1 opacity-40 group-hover:opacity-100 transition-opacity">
                <button
                    className="w-6 h-6 rounded-lg flex items-center justify-center hover:bg-primary/10 text-muted-foreground hover:text-primary"
                    onClick={(e) => { e.stopPropagation(); onSendToAI(n); }}
                    title="Ask AI about this"
                >
                    <MessageCircle className="w-3 h-3" />
                </button>
                <button
                    className="w-6 h-6 rounded-lg flex items-center justify-center hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                    onClick={(e) => { e.stopPropagation(); onDismiss(); }}
                    title="Dismiss"
                >
                    <X className="w-3 h-3" />
                </button>
            </div>

            {/* Clickable area to mark read */}
            <div
                className={cn("cursor-pointer", !n.is_read && "hover:opacity-90")}
                onClick={!n.is_read ? onMarkRead : undefined}
            >
                {/* Header row */}
                <div className="flex items-center gap-2 mb-2">
                    <div className="p-1.5 bg-accent rounded-lg flex-shrink-0">
                        <ToolIcon tool={n.source_tool} />
                    </div>
                    <PriorityBadge priority={displayPriority} />
                </div>

                <h4 className="text-sm font-medium mb-1 leading-snug pr-8">{displayTitle}</h4>

                {displayContent && (
                    <p className="text-xs text-muted-foreground mb-2 line-clamp-2">{displayContent}</p>
                )}

                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="w-3 h-3" />
                    <span>{relativeTime(n.created_at)}</span>
                    <span className="mx-1">•</span>
                    <span className="capitalize">{n.source_tool}</span>
                </div>
            </div>
        </div>
    );
}

/* ========================
   Empty state
   ======================== */
function EmptyState({ icon: Icon, title, description }: {
    icon: React.ElementType;
    title: string;
    description: string;
}) {
    return (
        <div className="flex flex-col items-center justify-center py-12 text-center px-4">
            <div className="w-12 h-12 rounded-2xl bg-accent flex items-center justify-center mb-4">
                <Icon className="w-6 h-6 text-muted-foreground" />
            </div>
            <h3 className="text-sm font-medium mb-1">{title}</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
        </div>
    );
}

/* ========================
   Task tools filter
   ======================== */
const TASK_TOOLS = new Set(["jira", "trello", "github"]);
const PRIORITIES = new Set(["low", "medium", "high", "urgent"]);
const ACTION_WORDS = [
    "action required",
    "asked you to",
    "assigned to you",
    "approve",
    "approval",
    "by friday",
    "by tomorrow",
    "due",
    "follow up",
    "need you to",
    "needs your",
    "please review",
    "reply",
    "respond",
    "review",
    "todo",
    "to-do",
];
const HIGH_PRIORITY_WORDS = [
    "action required",
    "approval",
    "approve",
    "asap",
    "attention",
    "blocked",
    "deadline",
    "due",
    "important",
    "needs attention",
    "urgent",
];

function metadataString(n: Notification, key: string): string | null {
    const value = n.metadata?.[key];
    return typeof value === "string" && value.trim() ? value.trim() : null;
}

function metadataBoolean(n: Notification, key: string): boolean {
    return n.metadata?.[key] === true;
}

function notificationText(n: Notification): string {
    return `${n.title} ${n.content ?? ""}`.toLowerCase();
}

function cleanActivityText(text: string): string {
    return text
        .replace(/[*|\-]/g, " ")
        .replace(/\s+([.,!?;:])/g, "$1")
        .replace(/\s+/g, " ")
        .trim();
}

function isTaskNotification(n: Notification): boolean {
    const category = metadataString(n, "category")?.toLowerCase();
    if (category && ["task", "tasks", "action", "action_item", "todo"].includes(category)) {
        return true;
    }
    if (metadataBoolean(n, "action_required")) return true;
    if (TASK_TOOLS.has(n.source_tool.toLowerCase())) return true;

    const text = notificationText(n);
    return ACTION_WORDS.some((word) => text.includes(word));
}

function getNotificationTitle(n: Notification): string {
    const attentionTitle =
        metadataString(n, "attention_title") ??
        metadataString(n, "extracted_title") ??
        metadataString(n, "summary_title");
    if (attentionTitle) return cleanActivityText(attentionTitle);

    if (metadataBoolean(n, "from_chat") && n.content) {
        const firstSentence = n.content.split(/[.\n]/)[0]?.trim();
        if (firstSentence) return cleanActivityText(firstSentence).slice(0, 120);
    }

    return cleanActivityText(n.title);
}

function getNotificationPriority(n: Notification): Notification["priority"] {
    const extractedPriority = metadataString(n, "extracted_priority")?.toLowerCase();
    if (extractedPriority && PRIORITIES.has(extractedPriority)) {
        return extractedPriority as Notification["priority"];
    }
    if (n.priority === "low" || n.priority === "medium") {
        const text = notificationText(n);
        if (HIGH_PRIORITY_WORDS.some((word) => text.includes(word))) return "high";
    }
    return n.priority;
}

/* ========================
   Props
   ======================== */
interface ContextPanelProps {
    isCollapsed: boolean;
    onToggleCollapse: () => void;
    onRefreshRef?: React.MutableRefObject<(() => void) | null>;
    /** Called when user clicks "Ask AI" on a notification card. */
    onSendToAI?: (message: string) => void;
}

/* ========================
   Component
   ======================== */
export function ContextPanel({ isCollapsed, onToggleCollapse, onRefreshRef, onSendToAI }: ContextPanelProps) {
    const [activeTab, setActiveTab] = useState<"workflows" | "notifications" | "tasks">("notifications");
    const { notifications, unreadCount, isLoading, markRead, markAllRead, dismiss, refresh } =
        useNotifications();
    const {
        workflows,
        isLoading: workflowsLoading,
        pause: pauseWorkflow,
        resume: resumeWorkflow,
        runNow: runWorkflowNow,
    } = useWorkflows();

    // Expose refresh to parent
    useEffect(() => {
        if (onRefreshRef) onRefreshRef.current = refresh;
        return () => {
            if (onRefreshRef) onRefreshRef.current = null;
        };
    }, [onRefreshRef, refresh]);

    const handleSendToAI = (n: Notification) => {
        const msg = `Help me with this notification from ${n.source_tool}:\n\n**${getNotificationTitle(n)}**${n.content ? `\n\n${n.content}` : ''}`;
        onSendToAI?.(msg);
    };
    const tasks = notifications.filter(isTaskNotification);
    const alerts = notifications.filter((n) => !isTaskNotification(n));

    if (isCollapsed) {
        const collapsedTabs = [
            { id: "notifications" as const, icon: Bell, label: "Alerts", badge: unreadCount },
            { id: "workflows" as const,     icon: Workflow,    label: "Workflows" },
            { id: "tasks" as const,         icon: ListChecks,  label: "Tasks" },
        ];
        return (
            <div className="w-16 h-full bg-context-bg border-l border-border flex flex-col items-center py-4 gap-2 rounded-l-2xl">
                <button
                    onClick={onToggleCollapse}
                    className="w-9 h-9 rounded-xl flex items-center justify-center hover:bg-accent transition-colors mb-1"
                >
                    <ChevronLeft className="w-4 h-4" />
                </button>
                {collapsedTabs.map((tab) => {
                    const Icon = tab.icon;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => { setActiveTab(tab.id); onToggleCollapse(); }}
                            title={tab.label}
                            className={cn(
                                "relative w-9 h-9 rounded-xl flex items-center justify-center hover:bg-accent transition-colors",
                                activeTab === tab.id ? "text-foreground bg-accent" : "text-muted-foreground"
                            )}
                        >
                            <Icon className="w-4 h-4" />
                            {tab.badge && tab.badge > 0 ? (
                                <span className="absolute top-0.5 right-0.5 min-w-[14px] h-[14px] px-0.5 bg-primary text-primary-foreground rounded-full text-[10px] flex items-center justify-center leading-none">
                                    {tab.badge > 9 ? "9+" : tab.badge}
                                </span>
                            ) : null}
                        </button>
                    );
                })}
            </div>
        );
    }

    const tabs = [
        { id: "workflows" as const, label: "Workflows", icon: Workflow },
        { id: "notifications" as const, label: "Alerts", icon: Bell, badge: unreadCount },
        { id: "tasks" as const, label: "Tasks", icon: ListChecks },
    ];

    return (
        <div className="w-full h-full bg-context-bg border-l border-border flex flex-col rounded-l-2xl">
            {/* Header */}
            <div className="p-4 border-b border-border flex items-center justify-between flex-shrink-0">
                <div>
                    <h2 className="font-semibold text-foreground">Activity</h2>
                    <p className="text-sm text-muted-foreground">Your workspace overview</p>
                </div>
                <button
                    onClick={onToggleCollapse}
                    className="w-9 h-9 rounded-xl flex items-center justify-center hover:bg-accent transition-colors"
                >
                    <ChevronRight className="w-4 h-4" />
                </button>
            </div>

            {/* Tab Bar */}
            <div className="flex-shrink-0 border-b border-border">
                <div className="flex">
                    {tabs.map((tab) => {
                        const Icon = tab.icon;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={cn(
                                    "relative flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px",
                                    activeTab === tab.id
                                        ? "border-primary text-foreground"
                                        : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
                                )}
                            >
                                <Icon className="w-4 h-4" />
                                <span className="hidden lg:inline">{tab.label}</span>
                                {tab.badge && tab.badge > 0 ? (
                                    <span className="absolute top-1.5 right-1 min-w-[16px] h-[16px] px-0.5 bg-primary text-primary-foreground rounded-full text-xs flex items-center justify-center">
                                        {tab.badge > 9 ? "9+" : tab.badge}
                                    </span>
                                ) : null}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-4 pb-4 custom-scrollbar">

                {/* ── Workflows ── */}
                {activeTab === "workflows" && (
                    <div className="space-y-3">
                        {workflowsLoading ? (
                            <NotificationSkeleton />
                        ) : workflows.length === 0 ? (
                            <EmptyState
                                icon={Workflow}
                                title="No workflows yet"
                                description="Create workflows from the AI chat to automate recurring work across connected tools."
                            />
                        ) : (
                            workflows.map((workflow) => (
                                <WorkflowCard
                                    key={workflow.id}
                                    workflow={workflow}
                                    onPause={() => pauseWorkflow(workflow.id)}
                                    onResume={() => resumeWorkflow(workflow.id)}
                                    onRunNow={() => runWorkflowNow(workflow.id)}
                                />
                            ))
                        )}
                    </div>
                )}

                {/* ── Alerts ── */}
                {activeTab === "notifications" && (
                    <div className="space-y-3">
                        {/* Sync status strip */}
                        <SyncStatusBar onSyncDone={refresh} />

                        {/* Mark all read */}
                        {unreadCount > 0 && (
                            <button
                                onClick={markAllRead}
                                className="w-full flex items-center justify-center gap-1.5 text-xs text-muted-foreground hover:text-foreground py-1.5 rounded-lg hover:bg-accent transition-colors"
                            >
                                <CheckCheck className="w-3.5 h-3.5" />
                                Mark all read
                            </button>
                        )}

                        {isLoading ? (
                            <NotificationSkeleton />
                        ) : alerts.length === 0 ? (
                            <EmptyState
                                icon={Bell}
                                title="No alerts yet"
                                description="Alerts appear here after you interact with connected tools via the AI chat. Try asking about your emails."
                            />
                        ) : (
                            alerts.map((n) => (
                                <NotificationCard
                                    key={n.id}
                                    n={n}
                                    onMarkRead={() => markRead(n.id)}
                                    onDismiss={() => dismiss(n.id)}
                                    onSendToAI={handleSendToAI}
                                />
                            ))
                        )}
                    </div>
                )}

                {/* ── Tasks ── */}
                {activeTab === "tasks" && (
                    <div className="space-y-3">
                        {isLoading ? (
                            <NotificationSkeleton />
                        ) : tasks.length === 0 ? (
                            <EmptyState
                                icon={ListChecks}
                                title="No tasks yet"
                                description="Connect JIRA, Trello, or GitHub, then use the AI chat to surface your open tasks and issues here."
                            />
                        ) : (
                            tasks.map((n) => (
                                <NotificationCard
                                    key={n.id}
                                    n={n}
                                    onMarkRead={() => markRead(n.id)}
                                    onDismiss={() => dismiss(n.id)}
                                    onSendToAI={handleSendToAI}
                                />
                            ))
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
