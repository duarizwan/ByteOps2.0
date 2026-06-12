"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useState, Suspense } from "react";
import { TopBar } from "@/components/dashboard/top-bar";
import { CollapsibleSidebar } from "@/components/dashboard/collapsible-sidebar";
import { ToolCard, type ToolMeta } from "@/components/dashboard/tool-card";
import { useToolConnections, type ToolType } from "@/hooks/use-tool-connections";
import { useConversations } from "@/hooks/use-conversations";
import { Loader2, AlertCircle, X } from "lucide-react";

// ── Tool registry (matches backend ToolType enum) ────────────────────────────

const TOOLS: ToolMeta[] = [
    {
        id: "gmail",
        name: "Gmail",
        description: "Read, send, and manage your emails with AI assistance.",
    },
    {
        id: "calendar",
        name: "Google Calendar",
        description: "Manage your schedule, create events, and get reminders.",
    },
    {
        id: "slack",
        name: "Slack",
        description: "Send messages and get notified from your Slack workspace.",
    },
    {
        id: "github",
        name: "GitHub",
        description: "Manage repos, issues, PRs, and automate your dev workflow.",
    },
    {
        id: "jira",
        name: "JIRA",
        description: "Track tasks, sprints, and project progress from your dashboard.",
    },
    {
        id: "trello",
        name: "Trello",
        description: "Visualise and manage your boards, lists, and cards.",
    },
    {
        id: "dropbox",
        name: "Dropbox",
        description: "Access and manage your files and folders via AI.",
    },
];

// ── Toast for callback messages ───────────────────────────────────────────────

function CallbackToast() {
    const params = useSearchParams();
    const connected = params.get("connected");
    const error = params.get("error");

    if (!connected && !error) return null;

    return (
        <div
            className={`fixed top-20 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-xl shadow-medium text-sm font-medium transition-all ${connected
                ? "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300"
                : "bg-destructive/10 text-destructive"
                }`}
        >
            {connected ? (
                <>✅ {TOOLS.find((t) => t.id === connected)?.name ?? connected} connected successfully!</>
            ) : (
                <><AlertCircle className="w-4 h-4" /> OAuth2 error: {error}</>
            )}
        </div>
    );
}

// ── Main Settings Page ────────────────────────────────────────────────────────

function SettingsContent() {
    const router = useRouter();
    const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
    const [dismissedError, setDismissedError] = useState<string | null>(null);
    const [connectError, setConnectError] = useState<string | null>(null);
    const { loading, error, isConnected, initiateConnect, disconnect, silentRefresh, refetch } = useToolConnections();
    const { conversations, isLoading: isLoadingConversations, deleteConversation } = useConversations();

    const handleConnect = async (id: ToolType) => {
        setConnectError(null);
        try {
            await initiateConnect(id);
        } catch (err) {
            setConnectError(err instanceof Error ? err.message : `Failed to connect ${id}`);
        }
    };

    return (
        <div className="h-screen flex flex-col bg-background overflow-hidden">
            <TopBar />
            <Suspense>
                <CallbackToast />
            </Suspense>

            <div className="flex flex-1 overflow-hidden">
                {/* Sidebar */}
                <div
                    className="flex-shrink-0 overflow-hidden transition-[width] duration-300 ease-in-out"
                    style={{ width: isLeftCollapsed ? 64 : 256 }}
                >
                    <div className="h-full" style={{ width: isLeftCollapsed ? 64 : 256 }}>
                        <CollapsibleSidebar
                            isCollapsed={isLeftCollapsed}
                            onToggleCollapse={() => setIsLeftCollapsed((v) => !v)}
                            conversations={conversations}
                            isLoadingConversations={isLoadingConversations}
                            activeConversationId={null}
                            onNewChat={() => router.push("/dashboard")}
                            onSelectConversation={(id) => router.push(`/dashboard?conversation=${id}`)}
                            onDeleteConversation={deleteConversation}
                        />
                    </div>
                </div>

                {/* Main content */}
                <div className="flex-1 overflow-y-auto p-8 bg-chat-bg m-3 rounded-2xl custom-scrollbar">
                    <div className="max-w-6xl mx-auto">
                        {/* Header */}
                        <div className="mb-8">
                            <h1 className="text-3xl font-semibold mb-2">Settings</h1>
                            <p className="text-muted-foreground">Manage your connected tools and integrations.</p>
                        </div>

                        {/* Connected Tools section */}
                        <section className="mb-10">
                            <h2 className="text-xl font-semibold mb-4">Connected Tools</h2>

                            {/* Connect error toast */}
                            {connectError && (
                                <div className="flex items-start gap-2 text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 px-4 py-3 rounded-xl mb-4 text-sm">
                                    <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                                    <span className="flex-1">{connectError}</span>
                                    <button onClick={() => setConnectError(null)} className="ml-1 hover:opacity-70 flex-shrink-0" aria-label="Dismiss">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                            )}

                            {/* Warning if backend status check failed */}
                            {error && dismissedError !== error && (
                                <div className="flex items-start gap-2 text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 px-4 py-3 rounded-xl mb-4 text-sm">
                                    <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                                    <span className="flex-1">
                                        Could not check connection statuses (is the backend running on{" "}
                                        <code className="text-xs bg-amber-100 dark:bg-amber-900/40 px-1 py-0.5 rounded">
                                            localhost:8000
                                        </code>
                                        ?). Showing all tools as disconnected.{" "}
                                        <button
                                            onClick={() => refetch()}
                                            className="underline underline-offset-2 hover:no-underline font-medium"
                                        >
                                            Retry
                                        </button>
                                    </span>
                                    <button
                                        onClick={() => setDismissedError(error)}
                                        className="ml-1 hover:opacity-70 transition-opacity flex-shrink-0"
                                        aria-label="Dismiss"
                                    >
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                            )}

                            {loading && (
                                <div className="flex items-center gap-2 text-muted-foreground mb-4 text-sm">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Checking connection statuses…
                                </div>
                            )}
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {TOOLS.map((tool) => (
                                    <ToolCard
                                        key={tool.id}
                                        tool={tool}
                                        isConnected={isConnected(tool.id as ToolType)}
                                        statusLoading={loading}
                                        onConnect={handleConnect}
                                        onDisconnect={(id) => disconnect(id)}
                                        onSilentRefresh={silentRefresh}
                                    />
                                ))}
                            </div>
                        </section>

                        {/* Account Settings section */}
                        <section>
                            <h2 className="text-xl font-semibold mb-4">Account Settings</h2>
                            <div className="bg-card rounded-2xl p-6 max-w-2xl shadow-soft">
                                <p className="text-sm text-muted-foreground mb-1">
                                    Your profile is managed via Clerk. Click your avatar in the top-right to update your name, email, and password.
                                </p>
                            </div>
                        </section>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default function SettingsPage() {
    return (
        <Suspense>
            <SettingsContent />
        </Suspense>
    );
}
