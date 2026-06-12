"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import {
    ChevronLeft,
    ChevronRight,
    ChevronDown,
    ChevronUp,
    Plus,
    MessageCircle,
    Trash2,
    Loader2,
    MoreHorizontal,
    Pencil,
    Check,
    X,
    AlertCircle,
    CheckCircle2,
    ExternalLink,
    Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ConversationSummary } from "@/hooks/use-conversations";
import { getBrandIconUrl } from "@/lib/brand-icons";
import { useToolConnections, type ToolType } from "@/hooks/use-tool-connections";

/* ========================
   Tool registry — IDs must match backend ToolType enum values
   ======================== */
const TOOL_REGISTRY = [
    { id: "gmail" as ToolType,    name: "Gmail"    },
    { id: "calendar" as ToolType, name: "Calendar" },
    { id: "slack" as ToolType,    name: "Slack"    },
    { id: "jira" as ToolType,     name: "JIRA"     },
    { id: "trello" as ToolType,   name: "Trello"   },
    { id: "dropbox" as ToolType,  name: "Dropbox"  },
    { id: "github" as ToolType,   name: "GitHub"   },
];

/* ========================
   API Key tool config — fields required per tool
   ======================== */
const OAUTH_ONLY_TOOLS = new Set<ToolType>(["gmail", "calendar"]);

interface ApiKeyField {
    key: string;
    label: string;
    placeholder: string;
    type: "text" | "password";
}
interface ApiKeyToolConfig {
    fields: ApiKeyField[];
    hint: string;
    scopes: string;
}

const API_KEY_TOOL_CONFIG: Partial<Record<ToolType, ApiKeyToolConfig>> = {
    github: {
        fields: [{ key: "token", label: "Personal Access Token", placeholder: "ghp_xxxxxxxxxxxxxxxxxxxx", type: "password" }],
        hint: "Generate at github.com → Settings → Developer settings → Personal access tokens",
        scopes: "repo, read:org, read:user",
    },
    jira: {
        fields: [
            { key: "workspace", label: "Workspace URL", placeholder: "yourcompany.atlassian.net", type: "text" },
            { key: "email", label: "Email Address", placeholder: "you@company.com", type: "text" },
            { key: "token", label: "API Token", placeholder: "ATATxxxxxxxxxxxxxxxxxxxxxxxx", type: "password" },
        ],
        hint: "Generate at id.atlassian.com → Security → API tokens",
        scopes: "read:jira-work, write:jira-work",
    },
    slack: {
        fields: [{ key: "token", label: "Bot Token", placeholder: "xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx", type: "password" }],
        hint: "From your Slack App → OAuth & Permissions → Bot User OAuth Token",
        scopes: "channels:read, chat:write, users:read",
    },
    trello: {
        fields: [
            { key: "api_key", label: "API Key", placeholder: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", type: "text" },
            { key: "token", label: "API Token", placeholder: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", type: "password" },
        ],
        hint: "Get both at trello.com/app-key",
        scopes: "read, write",
    },
    dropbox: {
        fields: [{ key: "token", label: "Access Token", placeholder: "sl.xxxxxxxxxxxxxxxxxxxxxxxxxx", type: "password" }],
        hint: "Generate at dropbox.com/developers/apps → your app → OAuth 2 → Generated access token",
        scopes: "files.content.read, files.metadata.read",
    },
};

/* ========================
   Date grouping helper
   ======================== */
function formatDate(isoString: string): string {
    const date = new Date(isoString);
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);

    if (date.toDateString() === now.toDateString()) return "Today";
    if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/* ========================
   Props
   ======================== */
interface CollapsibleSidebarProps {
    isCollapsed: boolean;
    onToggleCollapse: () => void;
    conversations: ConversationSummary[];
    isLoadingConversations: boolean;
    activeConversationId: string | null;
    onNewChat: () => void;
    onSelectConversation: (id: string) => void;
    onDeleteConversation: (id: string) => Promise<boolean>;
    onRenameConversation?: (id: string, title: string) => Promise<ConversationSummary | null>;
}

/* ========================
   ConversationItem — handles its own dropdown + inline rename state
   ======================== */
interface ConversationItemProps {
    chat: ConversationSummary;
    isActive: boolean;
    onSelect: () => void;
    onDelete: () => Promise<boolean>;
    onRename?: (title: string) => Promise<ConversationSummary | null>;
}

function ConversationItem({ chat, isActive, onSelect, onDelete, onRename }: ConversationItemProps) {
    const [menuOpen, setMenuOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [isRenaming, setIsRenaming] = useState(false);
    const [renameValue, setRenameValue] = useState(chat.title);
    const [isSavingRename, setIsSavingRename] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);
    const renameInputRef = useRef<HTMLInputElement>(null);

    // Close dropdown on outside click
    useEffect(() => {
        if (!menuOpen) return;
        const handleClickOutside = (e: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
                setMenuOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [menuOpen]);

    // Focus input when rename mode activates
    useEffect(() => {
        if (isRenaming) {
            renameInputRef.current?.focus();
            renameInputRef.current?.select();
        }
    }, [isRenaming]);

    const handleMenuClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        setMenuOpen((v) => !v);
    };

    const handleRenameClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        setMenuOpen(false);
        setRenameValue(chat.title);
        setIsRenaming(true);
    };

    const handleDeleteClick = async (e: React.MouseEvent) => {
        e.stopPropagation();
        setMenuOpen(false);
        if (!confirm("Delete this conversation?")) return;
        setIsDeleting(true);
        await onDelete();
        setIsDeleting(false);
    };

    const handleRenameSubmit = async () => {
        const trimmed = renameValue.trim();
        if (!trimmed || trimmed === chat.title) {
            setIsRenaming(false);
            return;
        }
        setIsSavingRename(true);
        await onRename?.(trimmed);
        setIsRenaming(false);
        setIsSavingRename(false);
    };

    const handleRenameKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter") {
            e.preventDefault();
            handleRenameSubmit();
        } else if (e.key === "Escape") {
            setIsRenaming(false);
            setRenameValue(chat.title);
        }
    };

    return (
        <div
            onClick={isRenaming ? undefined : onSelect}
            className={cn(
                "group relative flex items-center gap-2 p-2.5 rounded-xl transition-all",
                isRenaming ? "cursor-default" : "cursor-pointer",
                isActive
                    ? "bg-accent text-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            )}
        >
            <MessageCircle className="w-4 h-4 flex-shrink-0" />

            <div className="flex-1 min-w-0">
                {isRenaming ? (
                    // Inline rename input
                    <div className="flex items-center gap-1">
                        <input
                            ref={renameInputRef}
                            value={renameValue}
                            onChange={(e) => setRenameValue(e.target.value)}
                            onKeyDown={handleRenameKeyDown}
                            onBlur={handleRenameSubmit}
                            className="flex-1 min-w-0 text-sm bg-background border border-primary rounded px-1.5 py-0.5 outline-none text-foreground"
                            disabled={isSavingRename}
                        />
                        {isSavingRename ? (
                            <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />
                        ) : (
                            <>
                                <button
                                    onMouseDown={(e) => { e.preventDefault(); handleRenameSubmit(); }}
                                    className="text-green-500 hover:text-green-400 flex-shrink-0"
                                    title="Confirm"
                                >
                                    <Check className="w-3.5 h-3.5" />
                                </button>
                                <button
                                    onMouseDown={(e) => { e.preventDefault(); setIsRenaming(false); setRenameValue(chat.title); }}
                                    className="text-muted-foreground hover:text-foreground flex-shrink-0"
                                    title="Cancel"
                                >
                                    <X className="w-3.5 h-3.5" />
                                </button>
                            </>
                        )}
                    </div>
                ) : (
                    <>
                        <p className="text-sm truncate">{chat.title}</p>
                        <p className="text-xs opacity-60">{formatDate(chat.updated_at)}</p>
                    </>
                )}
            </div>

            {/* Three-dot menu button — only shown when not renaming */}
            {!isRenaming && (
                <div className="relative" ref={menuRef}>
                    <button
                        onClick={handleMenuClick}
                        disabled={isDeleting}
                        className={cn(
                            "w-6 h-6 rounded-lg flex items-center justify-center transition-opacity",
                            "opacity-0 group-hover:opacity-100",
                            isActive && "opacity-60",
                            "hover:bg-accent-foreground/10"
                        )}
                        title="More options"
                    >
                        {isDeleting ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                            <MoreHorizontal className="w-3.5 h-3.5" />
                        )}
                    </button>

                    {/* Dropdown menu */}
                    {menuOpen && (
                        <div className="absolute right-0 top-7 z-50 w-36 bg-popover border border-border rounded-xl shadow-lg overflow-hidden">
                            <button
                                onClick={handleRenameClick}
                                className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-accent transition-colors text-left"
                            >
                                <Pencil className="w-3.5 h-3.5" />
                                Rename
                            </button>
                            <button
                                onClick={handleDeleteClick}
                                className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-destructive/10 text-destructive transition-colors text-left"
                            >
                                <Trash2 className="w-3.5 h-3.5" />
                                Delete
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

/* ========================
   Connect Tool Modal
   ======================== */
function ConnectToolModal({ onClose }: { onClose: () => void }) {
    const { isConnected, initiateConnect, disconnect, connectViaApiKey } = useToolConnections();
    const [activeTab, setActiveTab] = useState<"apikey" | "oauth">("apikey");
    const [selectedTool, setSelectedTool] = useState<ToolType>("github");
    const [credentials, setCredentials] = useState<Record<string, string>>({});
    const [connecting, setConnecting] = useState(false);
    const [oauthBusy, setOauthBusy] = useState<ToolType | null>(null);
    const [disconnecting, setDisconnecting] = useState<ToolType | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [successTool, setSuccessTool] = useState<ToolType | null>(null);
    const overlayRef = useRef<HTMLDivElement>(null);
    const successTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("keydown", onKey);
            if (successTimerRef.current) clearTimeout(successTimerRef.current);
        };
    }, [onClose]);

    const handleSelectTool = (toolId: ToolType) => {
        if (OAUTH_ONLY_TOOLS.has(toolId)) {
            setActiveTab("oauth");
            return;
        }
        setSelectedTool(toolId);
        setCredentials({});
        setError(null);
    };

    const handleApiKeyConnect = async () => {
        setError(null);
        setConnecting(true);
        try {
            await connectViaApiKey(selectedTool, credentials);
            setSuccessTool(selectedTool);
            successTimerRef.current = setTimeout(onClose, 1200);
        } catch (err) {
            setError(err instanceof Error ? err.message : `Failed to connect ${selectedTool}`);
        } finally {
            setConnecting(false);
        }
    };

    const handleOAuthConnect = async (toolId: ToolType) => {
        setError(null);
        setOauthBusy(toolId);
        try {
            await initiateConnect(toolId);
        } catch (err) {
            setError(err instanceof Error ? err.message : `Failed to connect ${toolId}`);
        } finally {
            setOauthBusy(null);
        }
    };

    const handleDisconnect = async (toolId: ToolType) => {
        setError(null);
        setDisconnecting(toolId);
        try {
            await disconnect(toolId);
        } catch (err) {
            setError(err instanceof Error ? err.message : `Failed to disconnect ${toolId}`);
        } finally {
            setDisconnecting(null);
        }
    };

    const config = API_KEY_TOOL_CONFIG[selectedTool];
    const allFieldsFilled = config
        ? config.fields.every((f) => (credentials[f.key] ?? "").trim().length > 0)
        : false;

    return (
        <div
            ref={overlayRef}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
        >
            <div className="w-full max-w-sm mx-4 bg-card border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                    <div>
                        <h2 className="font-semibold text-foreground text-base">Connect a Tool</h2>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            {activeTab === "apikey" ? "Paste your credentials — no redirect needed" : "Select a tool to connect via OAuth"}
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        aria-label="Close"
                        className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-border" role="tablist">
                    <button
                        role="tab"
                        aria-selected={activeTab === "apikey"}
                        aria-controls="panel-apikey"
                        id="tab-apikey"
                        onClick={() => setActiveTab("apikey")}
                        className={cn(
                            "flex-1 py-2.5 text-xs font-medium transition-colors border-b-2",
                            activeTab === "apikey"
                                ? "border-primary text-foreground"
                                : "border-transparent text-muted-foreground hover:text-foreground"
                        )}
                    >
                        API Key
                    </button>
                    <button
                        role="tab"
                        aria-selected={activeTab === "oauth"}
                        aria-controls="panel-oauth"
                        id="tab-oauth"
                        onClick={() => setActiveTab("oauth")}
                        className={cn(
                            "flex-1 py-2.5 text-xs font-medium transition-colors border-b-2",
                            activeTab === "oauth"
                                ? "border-primary text-foreground"
                                : "border-transparent text-muted-foreground hover:text-foreground"
                        )}
                    >
                        OAuth
                    </button>
                </div>

                {/* Error banner */}
                {error && (
                    <div className="mx-4 mt-3 flex items-start gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 px-3 py-2 rounded-xl">
                        <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                        <span className="flex-1">{error}</span>
                        <button onClick={() => setError(null)} aria-label="Dismiss error" className="flex-shrink-0 hover:opacity-70">
                            <X className="w-3.5 h-3.5" />
                        </button>
                    </div>
                )}

                {/* API Key Panel */}
                {activeTab === "apikey" && (
                    <div role="tabpanel" id="panel-apikey" aria-labelledby="tab-apikey" className="p-4 flex flex-col gap-4 max-h-[60vh] overflow-y-auto custom-scrollbar">
                        {/* Tool chip selector */}
                        <div>
                            <p className="text-xs text-muted-foreground mb-2 font-medium uppercase tracking-wide">Platform</p>
                            <div className="flex flex-wrap gap-2">
                                {TOOL_REGISTRY.map((tool) => {
                                    const isOAuthOnly = OAUTH_ONLY_TOOLS.has(tool.id);
                                    const iconUrl = getBrandIconUrl(tool.id);
                                    return (
                                        <button
                                            key={tool.id}
                                            onClick={() => handleSelectTool(tool.id)}
                                            title={isOAuthOnly ? `${tool.name} requires OAuth` : undefined}
                                            className={cn(
                                                "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium transition-colors",
                                                isOAuthOnly
                                                    ? "opacity-40 cursor-pointer border-border text-muted-foreground"
                                                    : selectedTool === tool.id
                                                    ? "border-primary bg-primary/10 text-primary"
                                                    : "border-border text-muted-foreground hover:border-primary/50 hover:text-foreground"
                                            )}
                                        >
                                            {iconUrl ? (
                                                // eslint-disable-next-line @next/next/no-img-element
                                                <img src={iconUrl} alt="" width={13} height={13} className="object-contain rounded-sm" loading="lazy" />
                                            ) : (
                                                <span className="w-3 h-3 rounded-sm bg-muted flex items-center justify-center text-[9px] font-bold">
                                                    {tool.name[0]}
                                                </span>
                                            )}
                                            {tool.name}
                                            {isOAuthOnly && <span className="text-[9px] opacity-60 ml-0.5">OAuth only</span>}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Dynamic credential form */}
                        {config && (
                            <div className="flex flex-col gap-3">
                                {/* Scopes note */}
                                <div className="flex items-start gap-2 bg-primary/5 border border-primary/15 rounded-lg px-3 py-2">
                                    <AlertCircle className="w-3.5 h-3.5 text-primary flex-shrink-0 mt-0.5" />
                                    <span className="text-xs text-primary/80">Required access: {config.scopes}</span>
                                </div>

                                {/* Fields */}
                                {config.fields.map((field) => (
                                    <div key={field.key}>
                                        <label className="text-xs text-muted-foreground font-medium uppercase tracking-wide block mb-1.5">
                                            {field.label}
                                        </label>
                                        <input
                                            type={field.type}
                                            placeholder={field.placeholder}
                                            value={credentials[field.key] ?? ""}
                                            onChange={(e) =>
                                                setCredentials((prev) => ({ ...prev, [field.key]: e.target.value }))
                                            }
                                            className="w-full bg-background border border-border rounded-lg px-3 py-2 text-xs font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary transition-colors"
                                        />
                                    </div>
                                ))}

                                {/* Hint */}
                                <p className="text-xs text-muted-foreground leading-relaxed">{config.hint}</p>

                                {/* Connect button / success state */}
                                {successTool === selectedTool ? (
                                    <div className="flex items-center justify-center gap-2 py-2.5 rounded-xl bg-emerald-500/10 text-emerald-500 text-sm font-medium border border-emerald-500/20">
                                        <CheckCircle2 className="w-4 h-4" /> Connected
                                    </div>
                                ) : (
                                    <button
                                        onClick={handleApiKeyConnect}
                                        disabled={!allFieldsFilled || connecting}
                                        className="flex items-center justify-center gap-2 py-2.5 rounded-xl bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                                    >
                                        {connecting ? (
                                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                        ) : (
                                            <Check className="w-3.5 h-3.5" />
                                        )}
                                        {connecting ? "Connecting…" : `Connect ${TOOL_REGISTRY.find(t => t.id === selectedTool)?.name ?? selectedTool}`}
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {/* OAuth Panel */}
                {activeTab === "oauth" && (
                    <div role="tabpanel" id="panel-oauth" aria-labelledby="tab-oauth" className="flex flex-col gap-1 p-3 max-h-[60vh] overflow-y-auto custom-scrollbar">
                        {TOOL_REGISTRY.map((tool) => {
                            const connected = isConnected(tool.id);
                            const iconUrl = getBrandIconUrl(tool.id);
                            const isOAuthBusy = oauthBusy === tool.id;
                            const isDisconnectingThis = disconnecting === tool.id;
                            const busy = isOAuthBusy || isDisconnectingThis;

                            return (
                                <div
                                    key={tool.id}
                                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-accent/50 transition-colors"
                                >
                                    <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center flex-shrink-0 overflow-hidden">
                                        {iconUrl ? (
                                            // eslint-disable-next-line @next/next/no-img-element
                                            <img src={iconUrl} alt={tool.name} width={20} height={20} className="object-contain" loading="lazy" />
                                        ) : (
                                            <span className="text-xs font-bold text-muted-foreground">{tool.name[0]}</span>
                                        )}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-foreground">{tool.name}</p>
                                        {connected ? (
                                            <p className="text-xs text-emerald-500 flex items-center gap-1">
                                                <CheckCircle2 className="w-3 h-3" /> Connected
                                            </p>
                                        ) : (
                                            <p className="text-xs text-muted-foreground">Not connected</p>
                                        )}
                                    </div>
                                    {connected ? (
                                        <button
                                            onClick={() => handleDisconnect(tool.id)}
                                            disabled={busy}
                                            className="text-xs px-3 py-1.5 rounded-lg bg-destructive/10 text-destructive hover:bg-destructive hover:text-white transition-colors disabled:opacity-50 flex items-center gap-1"
                                        >
                                            {isDisconnectingThis ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                                            Disconnect
                                        </button>
                                    ) : (
                                        <button
                                            onClick={() => handleOAuthConnect(tool.id)}
                                            disabled={busy}
                                            className="text-xs px-3 py-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center gap-1"
                                        >
                                            {isOAuthBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <ExternalLink className="w-3 h-3" />}
                                            Connect
                                        </button>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}

                {/* Footer */}
                <div className="px-5 py-3 border-t border-border">
                    <p className="text-xs text-muted-foreground text-center">
                        {activeTab === "apikey"
                            ? "Credentials are encrypted and stored securely."
                            : "You'll be redirected to the tool's OAuth page to authorise access."}
                    </p>
                </div>
            </div>
        </div>
    );
}

/* ========================
   Main CollapsibleSidebar Component
   ======================== */
export function CollapsibleSidebar({
    isCollapsed,
    onToggleCollapse,
    conversations,
    isLoadingConversations,
    activeConversationId,
    onNewChat,
    onSelectConversation,
    onDeleteConversation,
    onRenameConversation,
}: CollapsibleSidebarProps) {
    const [showConnectModal, setShowConnectModal] = useState(false);
    const [toolsExpanded, setToolsExpanded] = useState(true);

    // Live connection status from the backend
    const { isConnected } = useToolConnections();

    const getStatusColor = (toolId: ToolType) => {
        if (isConnected(toolId))
            return "bg-success shadow-[0_0_6px_2px_rgba(34,197,94,0.45)] transition-all duration-300";
        return "bg-muted-foreground transition-all duration-300";
    };

    return (
        <div
            className={cn(
                "bg-sidebar-bg border-r border-sidebar-border transition-all duration-300 flex flex-col h-full rounded-r-2xl",
                isCollapsed ? "w-16" : "w-64"
            )}
        >
            {/* Collapse Toggle */}
            <div className={cn("p-3 flex items-center", isCollapsed ? "flex-col gap-1" : "justify-between")}>
                <button
                    onClick={onToggleCollapse}
                    className="w-9 h-9 hover:bg-accent rounded-xl transition-colors flex items-center justify-center"
                    title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                >
                    {isCollapsed ? (
                        <ChevronRight className="w-4 h-4" />
                    ) : (
                        <ChevronLeft className="w-4 h-4" />
                    )}
                </button>
                {/* New chat button visible in collapsed mode */}
                {isCollapsed && (
                    <button
                        onClick={onNewChat}
                        className="w-9 h-9 hover:bg-accent rounded-xl transition-colors flex items-center justify-center text-muted-foreground hover:text-foreground"
                        title="New Chat"
                    >
                        <Plus className="w-4 h-4" />
                    </button>
                )}
            </div>

            {/* Chat History Section */}
            {!isCollapsed && (
                <div className="px-3 mb-2 flex-1 flex flex-col min-h-0">
                    <button
                        onClick={onNewChat}
                        className="w-full bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-medium py-2.5 rounded-xl flex items-center justify-center gap-2 mb-3 transition-colors"
                    >
                        <Plus className="w-4 h-4" />
                        New Chat
                    </button>

                    <p className="text-xs font-semibold tracking-wider text-muted-foreground mb-2 px-3 uppercase">Chats</p>

                    <div className="space-y-1 flex-1 overflow-y-auto custom-scrollbar pr-1">
                        {isLoadingConversations ? (
                            <div className="flex items-center justify-center py-3">
                                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                            </div>
                        ) : conversations.length === 0 ? (
                            <p className="text-xs text-muted-foreground px-3 py-2 italic">
                                No conversations yet
                            </p>
                        ) : (
                            conversations.map((chat) => (
                                <ConversationItem
                                    key={chat.id}
                                    chat={chat}
                                    isActive={activeConversationId === chat.id}
                                    onSelect={() => onSelectConversation(chat.id)}
                                    onDelete={() => onDeleteConversation(chat.id)}
                                    onRename={
                                        onRenameConversation
                                            ? (title) => onRenameConversation(chat.id, title)
                                            : undefined
                                    }
                                />
                            ))
                        )}
                    </div>
                </div>
            )}

            {/* Runs nav link — prominent */}
            <div className={cn("flex-shrink-0 border-t border-border", isCollapsed ? "px-2 py-2" : "px-3 py-2")}>
                <Link
                    href="/runs"
                    title="Execution Trace"
                    className={cn(
                        "flex items-center gap-3 rounded-xl transition-all font-medium",
                        "bg-primary/10 text-primary hover:bg-primary/20 border border-primary/20",
                        isCollapsed ? "justify-center p-2.5" : "px-3 py-2.5"
                    )}
                >
                    <Activity className="w-4 h-4 flex-shrink-0" />
                    {!isCollapsed && (
                        <span className="text-sm flex-1">Execution Trace</span>
                    )}
                </Link>
            </div>

            {/* Tool Connections Header — collapsible */}
            {!isCollapsed && (
                <div className="px-3 flex-shrink-0 border-t border-border pt-3 pb-1">
                    <button
                        onClick={() => setToolsExpanded((v) => !v)}
                        className="w-full flex items-center justify-between px-1 group"
                    >
                        <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Tools</p>
                        <span className="text-muted-foreground group-hover:text-foreground transition-colors">
                            {toolsExpanded
                                ? <ChevronUp className="w-3.5 h-3.5" />
                                : <ChevronDown className="w-3.5 h-3.5" />}
                        </span>
                    </button>
                </div>
            )}

            {/* Tool List */}
            {(isCollapsed || toolsExpanded) && (
            <div className="flex flex-col gap-1 px-2 overflow-y-auto custom-scrollbar pb-2">
                {TOOL_REGISTRY.map((tool) => {
                    const connected = isConnected(tool.id);
                    const iconUrl = getBrandIconUrl(tool.id);
                    return (
                        <Link
                            key={tool.id}
                            href="/settings"
                            title={connected ? `${tool.name} — connected` : `${tool.name} — click to connect`}
                            className={cn(
                                "relative flex items-center gap-3 p-3 rounded-xl transition-all",
                                connected
                                    ? "text-foreground hover:bg-accent"
                                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                            )}
                        >
                            {/* Icon wrapped in relative container so the status dot overlays it */}
                            <div className="relative flex-shrink-0 w-4 h-4">
                                {iconUrl ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img src={iconUrl} alt={tool.name} width={16} height={16} className="w-4 h-4 object-contain" loading="lazy" />
                                ) : (
                                    <div className="w-4 h-4 rounded bg-muted" />
                                )}
                                {isCollapsed && (
                                    <div className={cn("absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full ring-1 ring-sidebar-bg", getStatusColor(tool.id))} />
                                )}
                            </div>

                            {!isCollapsed && (
                                <>
                                    <span className="text-sm font-medium flex-1 truncate">
                                        {tool.name}
                                    </span>
                                    <div className={cn("w-2 h-2 rounded-full flex-shrink-0", getStatusColor(tool.id))} />
                                </>
                            )}
                        </Link>
                    );
                })}
            </div>
            )}

            {/* Connect New Tool — opens modal */}
            {!isCollapsed && toolsExpanded && (
                <div className="p-3">
                    <button
                        onClick={() => setShowConnectModal(true)}
                        className="w-full bg-accent hover:bg-accent/80 text-accent-foreground text-sm font-medium py-2.5 rounded-xl flex items-center justify-center gap-2 transition-colors"
                    >
                        <Plus className="w-4 h-4" />
                        Connect New Tool
                    </button>
                </div>
            )}

            {showConnectModal && (
                <ConnectToolModal onClose={() => setShowConnectModal(false)} />
            )}
        </div>
    );
}
