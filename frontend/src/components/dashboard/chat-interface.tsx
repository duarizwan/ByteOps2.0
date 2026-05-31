"use client";

import Link from "next/link";
import { useState, useRef, useEffect } from "react";
import { Send, User, Paperclip, Mic, Mail, ExternalLink, Loader2, HelpCircle, X, AlertCircle } from "lucide-react";
import { useAuth } from "@clerk/nextjs";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";
import { useConversations, ConversationMessage } from "@/hooks/use-conversations";
import { ByteOpsLogoMark } from "@/lib/brand-icons";
import { useToolConnections } from "@/hooks/use-tool-connections";
import { TOOL_CAPABILITIES } from "@/lib/tool-capabilities";
import { api } from "@/lib/api";
import { classifyError } from "@/lib/classify-error";
import type { ActionErrorCategory } from "@/lib/action-center-types";

/* ========================
   Types
   ======================== */
interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
    toolCalls?: ToolCall[];
    stage?: string;
    errorClass?: ActionErrorCategory;
}

interface ToolCall {
    tool: string;
    args?: string;
    result?: string;
    status: "pending" | "done" | "error";
}

interface ApprovalRequest {
    run_id: string;
    tool: string;
    action: string;
    input: Record<string, unknown>;
    risk: "read" | "write" | "external_send" | "destructive";
    reason: string;
}

interface WorkflowDraftAction {
    tool: string;
    label: string;
}

interface WorkflowDraft {
    run_id: string;
    name: string;
    trigger: {
        type?: string;
        label?: string;
    };
    actions: WorkflowDraftAction[];
    missing_tools: string[];
    review_reasons: string[];
}

interface EmailResult {
    subject: string;
    date: string;
    from: string;
    snippet?: string;
}

interface ChatInterfaceProps {
    /** The currently active conversation UUID, or null for a fresh chat. */
    conversationId: string | null;
    /** Called with the new conversation ID when the first message creates a thread. */
    onConversationCreated: (id: string) => void;
    /** Pre-fill the input with this message (from the Ask AI notification bridge). */
    initialMessage?: string | null;
    /** Called after initialMessage has been consumed and input set, so parent can clear it. */
    onInitialMessageConsumed?: () => void;
}

const WELCOME_MESSAGE: Message = {
    id: "welcome",
    role: "assistant",
    content:
        "Hello! I can help with Gmail, Calendar, GitHub and more.",
    timestamp: new Date(),
};

const SUGGESTED_PROMPTS = [
    "Summarize emails",
    "My calendar today",
    "Open PRs",
    "Show high-priority tasks",
];

const STAGE_LABELS = {
    understanding:  "Understanding request…",
    routing:        "Routing to specialist agent…",
    awaiting:       "Waiting for approval…",
    finalizing:     "Finalizing response…",
} as const;

const CHAT_ERROR_MESSAGES: Record<string, { text: string; actionLabel?: string; actionPath?: string }> = {
    oauth_missing:   { text: "A required integration isn't connected.", actionLabel: "Go to Settings →", actionPath: "/settings" },
    no_results:      { text: "No results found for your request." },
    auth:            { text: "Authentication failed. Please sign out and sign back in." },
    timeout:         { text: "This took longer than expected. Please try again." },
    mcp_unavailable: { text: "A service is temporarily unavailable. Please try again." },
    backend_down:    { text: "Can't reach ByteOps. Check your connection and retry." },
    unknown:         { text: "Something went wrong. Please try again." },
};

const SUPPORTED_WORKFLOW_ACTIONS: WorkflowDraftAction[] = [
    { tool: "gmail", label: "Review Gmail activity" },
    { tool: "slack", label: "Review Slack activity" },
    { tool: "jira", label: "Review Jira items" },
    { tool: "github", label: "Review GitHub activity" },
    { tool: "calendar", label: "Review Calendar events" },
    { tool: "dropbox", label: "Review Dropbox files" },
    { tool: "byteops", label: "List urgent tasks" },
];

/* ========================
   Utility Components
   ======================== */
const EmailCard = ({ data }: { data: EmailResult }) => {
    return (
        <div className="mt-2 bg-background border border-border rounded-lg p-3 text-sm shadow-sm flex flex-col gap-2">
            <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-blue-500" />
                <span className="font-semibold truncate flex-1">{data.subject}</span>
                <span className="text-xs text-muted-foreground whitespace-nowrap">{data.date}</span>
            </div>
            <div className="flex justify-between items-end">
                <span className="text-xs text-muted-foreground truncate" title={data.from}>
                    From: {data.from.split("<")[0].trim()}
                </span>
                <button className="text-xs text-primary hover:underline flex items-center gap-1">
                    View full <ExternalLink className="w-3 h-3" />
                </button>
            </div>
            {data.snippet && (
                <p className="text-xs text-muted-foreground mt-1 line-clamp-2 italic border-l-2 pl-2 border-primary/30">
                    &ldquo;{data.snippet}&rdquo;
                </p>
            )}
        </div>
    );
};

/* ========================
   Approval Card
   ======================== */
function ApprovalCard({ approval, onApprove, onReject }: {
    approval: ApprovalRequest;
    onApprove: () => void;
    onReject: () => void;
}) {
    const riskBorder: Record<string, string> = {
        destructive: "border-red-500/40 bg-red-500/5",
        external_send: "border-orange-500/40 bg-orange-500/5",
        write: "border-yellow-500/40 bg-yellow-500/5",
        read: "border-green-500/40 bg-green-500/5",
    };
    return (
        <div className={"rounded-xl border p-4 my-2 " + (riskBorder[approval.risk] || "border-border")}>
            <p className="text-xs font-semibold text-muted-foreground mb-1">Action requires approval</p>
            <p className="text-sm font-medium mb-1">{approval.tool} → {approval.action}</p>
            <p className="text-xs text-muted-foreground mb-2">{approval.reason}</p>
            {Object.keys(approval.input).length > 0 && (
                <pre className="text-xs bg-accent/50 rounded p-2 mb-3 overflow-x-auto max-h-32 whitespace-pre-wrap">
                    {JSON.stringify(approval.input, null, 2)}
                </pre>
            )}
            <div className="flex gap-2">
                <button onClick={onApprove} className="px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:opacity-90">
                    Approve
                </button>
                <button onClick={onReject} className="px-3 py-1.5 text-xs font-medium rounded-lg bg-destructive/10 text-destructive hover:bg-destructive/20">
                    Reject
                </button>
            </div>
        </div>
    );
}

function WorkflowDraftCard({ draft, onDraftChange, onApprove, onDismiss, isApproving, approveError }: {
    draft: WorkflowDraft;
    onDraftChange: (draft: WorkflowDraft) => void;
    onApprove: () => void;
    onDismiss: () => void;
    isApproving: boolean;
    approveError?: string | null;
}) {
    const [selectedActionTool, setSelectedActionTool] = useState(SUPPORTED_WORKFLOW_ACTIONS[0].tool);

    const updateActionLabel = (index: number, label: string) => {
        onDraftChange({
            ...draft,
            actions: draft.actions.map((action, actionIndex) =>
                actionIndex === index ? { ...action, label } : action
            ),
        });
    };

    const removeAction = (index: number) => {
        onDraftChange({
            ...draft,
            actions: draft.actions.filter((_, actionIndex) => actionIndex !== index),
        });
    };

    const addDraftAction = () => {
        const action = SUPPORTED_WORKFLOW_ACTIONS.find((item) => item.tool === selectedActionTool);
        if (!action) return;
        onDraftChange({
            ...draft,
            actions: [...draft.actions, { ...action }],
        });
    };

    return (
        <div className="rounded-xl border border-yellow-500/40 bg-yellow-500/5 p-4 my-2">
            <p className="text-xs font-semibold text-muted-foreground mb-1">Workflow draft needs review</p>
            <div className="space-y-3 text-xs text-muted-foreground">
                <div>
                    <label className="block font-medium text-foreground mb-1">Name</label>
                    <input
                        value={draft.name}
                        onChange={(event) => onDraftChange({ ...draft, name: event.target.value })}
                        className="w-full rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground outline-none focus:ring-2 focus:ring-primary"
                    />
                </div>
                <div>
                    <label className="block font-medium text-foreground mb-1">Trigger</label>
                    <input
                        value={draft.trigger.label || ""}
                        onChange={(event) => onDraftChange({
                            ...draft,
                            trigger: { ...draft.trigger, label: event.target.value },
                        })}
                        className="w-full rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground outline-none focus:ring-2 focus:ring-primary"
                    />
                </div>
                <div>
                    <p className="font-medium text-foreground mb-1">Actions</p>
                    <div className="mt-1 space-y-1">
                        {draft.actions.map((action, index) => (
                            <div key={`${action.tool}-${index}`} className="rounded-lg bg-background/60 p-2 space-y-1">
                                <input
                                    value={action.label}
                                    onChange={(event) => updateActionLabel(index, event.target.value)}
                                    className="w-full rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground outline-none focus:ring-2 focus:ring-primary"
                                />
                                <button
                                    type="button"
                                    onClick={() => removeAction(index)}
                                    className="text-xs text-destructive hover:underline"
                                >
                                    Remove action
                                </button>
                            </div>
                        ))}
                    </div>
                    <div className="mt-2 flex flex-col sm:flex-row gap-2">
                        <select
                            value={selectedActionTool}
                            onChange={(event) => setSelectedActionTool(event.target.value)}
                            className="flex-1 rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground outline-none focus:ring-2 focus:ring-primary"
                        >
                            {SUPPORTED_WORKFLOW_ACTIONS.map((action) => (
                                <option key={action.tool} value={action.tool}>
                                    {action.label}
                                </option>
                            ))}
                        </select>
                        <button
                            type="button"
                            onClick={addDraftAction}
                            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent text-foreground hover:bg-accent/80"
                        >
                            Add action
                        </button>
                    </div>
                </div>
                {draft.review_reasons.length > 0 && (
                    <div className="space-y-1">
                        {draft.review_reasons.map((reason, index) => (
                            <p key={index}>{reason}</p>
                        ))}
                    </div>
                )}
            </div>
            {approveError && (
                <p className="text-xs text-destructive mt-2">{approveError}</p>
            )}
            <div className="flex gap-2 mt-3">
                <button
                    onClick={onApprove}
                    disabled={isApproving || !draft.name.trim() || draft.actions.length === 0}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-60"
                >
                    {isApproving ? "Saving…" : "Approve draft"}
                </button>
                <button
                    onClick={onDismiss}
                    disabled={isApproving}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent text-foreground hover:bg-accent/80 disabled:opacity-60"
                >
                    Dismiss
                </button>
            </div>
        </div>
    );
}

/* ========================
   Component
   ======================== */
export function ChatInterface({
    conversationId,
    onConversationCreated,
    initialMessage,
    onInitialMessageConsumed,
}: ChatInterfaceProps) {
    const { getToken } = useAuth();
    const { getConversationDetail } = useConversations();
    const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
    const [input, setInput] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const [isLoadingHistory, setIsLoadingHistory] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [attachedFile, setAttachedFile] = useState<File | null>(null);
    const [showHelp, setShowHelp] = useState(false);
    const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null);
    const [pendingWorkflowDraft, setPendingWorkflowDraft] = useState<WorkflowDraft | null>(null);
    const [isApprovingWorkflowDraft, setIsApprovingWorkflowDraft] = useState(false);
    const [workflowDraftError, setWorkflowDraftError] = useState<string | null>(null);
    const helpRef = useRef<HTMLDivElement>(null);
    const { connections } = useToolConnections();
    const connectedTools = connections.filter(c => c.status === "connected");

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // ── Ask AI bridge: pre-fill input from notification panel ──────────────────
    useEffect(() => {
        if (initialMessage) {
            setInput(initialMessage);
            onInitialMessageConsumed?.();
            // Focus textarea so user can immediately edit/send
            setTimeout(() => textareaRef.current?.focus(), 50);
        }
    }, [initialMessage, onInitialMessageConsumed]);

    // ── Load conversation history when conversationId changes ─────────────────
    useEffect(() => {
        if (!conversationId) {
            // null = new chat: reset to welcome message
            setMessages([WELCOME_MESSAGE]);
            return;
        }

        let cancelled = false;
        setIsLoadingHistory(true);

        getConversationDetail(conversationId).then((detail) => {
            if (cancelled) return;
            if (!detail) {
                setMessages([WELCOME_MESSAGE]);
            } else {
                const loaded: Message[] = detail.messages.map((m: ConversationMessage) => ({
                    id: m.id,
                    role: m.role,
                    content: m.content,
                    timestamp: new Date(m.created_at),
                }));
                setMessages(loaded.length > 0 ? loaded : [WELCOME_MESSAGE]);
            }
            setIsLoadingHistory(false);
        });

        return () => { cancelled = true; };
    }, [conversationId, getConversationDetail]);

    useEffect(() => {
        function handleClickOutside(e: MouseEvent) {
            if (helpRef.current && !helpRef.current.contains(e.target as Node)) {
                setShowHelp(false);
            }
        }
        if (showHelp) {
            document.addEventListener("mousedown", handleClickOutside);
            return () => document.removeEventListener("mousedown", handleClickOutside);
        }
    }, [showHelp]);

    // ── Send message ──────────────────────────────────────────────────────────
    /** Pass an explicit `message` to send a suggested prompt without going through the input state. */
    const handleSend = async (message?: string) => {
        const baseText = (message ?? input).trim();
        const fileNote = attachedFile ? `\n[Attached file: ${attachedFile.name}]` : "";
        const userText = baseText + fileNote;
        if (!userText.trim() || isTyping) return;

        if (!message) {
            setInput("");
            if (textareaRef.current) {
                textareaRef.current.style.height = "auto";
            }
        }
        setAttachedFile(null);
        setIsTyping(true);

        const userMessage: Message = {
            id: Date.now().toString(),
            role: "user",
            content: userText,
            timestamp: new Date(),
        };

        const assistantMessageId = (Date.now() + 1).toString();

        setMessages((prev) => [
            ...prev,
            userMessage,
            { id: assistantMessageId, role: "assistant", content: "", timestamp: new Date(), toolCalls: [], stage: STAGE_LABELS.understanding },
        ]);

        try {
            const token = await getToken();

            const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const response = await fetch(`${API_BASE}/api/chat`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    message: userText,
                    conversation_id: conversationId,
                }),
            });

            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split("\n");

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        const dataStr = line.slice(6);
                        if (!dataStr) continue;

                        try {
                            const event = JSON.parse(dataStr);

                            // Capture conversation_id from the done event
                            if (event.type === "done" && event.conversation_id) {
                                onConversationCreated(event.conversation_id);
                            }

                            if (event.type === "approval_required") {
                                setPendingApproval({
                                    run_id: event.run_id,
                                    tool: event.tool,
                                    action: event.action,
                                    input: event.input || {},
                                    risk: event.risk,
                                    reason: event.reason,
                                });
                            }
                            if (event.type === "workflow_draft") {
                                setPendingWorkflowDraft({
                                    run_id: event.run_id,
                                    name: event.name,
                                    trigger: event.trigger || {},
                                    actions: Array.isArray(event.actions) ? event.actions : [],
                                    missing_tools: Array.isArray(event.missing_tools) ? event.missing_tools : [],
                                    review_reasons: Array.isArray(event.review_reasons) ? event.review_reasons : [],
                                });
                                // Draft is ready — unblock input so user can edit while reviewing
                                setIsTyping(false);
                            }

                            setMessages((prev) =>
                                prev.map((msg) => {
                                    if (msg.id !== assistantMessageId) return msg;

                                    let newContent = msg.content;
                                    const newToolCalls = [...(msg.toolCalls || [])];
                                    let newStage = msg.stage;

                                    if ((event.type === "delta" || event.type === "text") && event.content) {
                                        newContent += event.content;
                                        newStage = undefined; // content flowing — clear stage label
                                    } else if (event.type === "tool_call_start") {
                                        newStage = STAGE_LABELS.routing;
                                        newToolCalls.push({
                                            tool: event.tool,
                                            args: event.args,
                                            status: "pending",
                                        });
                                    } else if (event.type === "tool_call_result") {
                                        const tc = newToolCalls.find(
                                            (t) => t.tool === event.tool && t.status === "pending"
                                        );
                                        if (tc) {
                                            tc.status = "done";
                                            tc.result = event.content;
                                        }
                                    } else if (event.type === "approval_required") {
                                        newStage = STAGE_LABELS.awaiting;
                                    } else if (event.type === "done") {
                                        newStage = undefined;
                                    } else if (event.type === "error") {
                                        newStage = undefined;
                                        return { ...msg, content: "", toolCalls: newToolCalls, stage: undefined, errorClass: classifyError(event.content ?? "") };
                                    }

                                    return { ...msg, content: newContent, toolCalls: newToolCalls, stage: newStage };
                                })
                            );
                        } catch (e) {
                            console.error("Failed to parse SSE JSON:", e, dataStr);
                        }
                    }
                }
            }
        } catch (error) {
            console.error("Chat error:", error);
            setMessages((prev) =>
                prev.map((msg) =>
                    msg.id === assistantMessageId
                        ? { ...msg, stage: undefined, errorClass: "backend_down" }
                        : msg
                )
            );
        } finally {
            setIsTyping(false);
        }
    };

    const handleApprove = async () => {
        if (!pendingApproval) return;
        const token = await getToken();
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const response = await fetch(apiBase + "/api/agent-runs/" + pendingApproval.run_id + "/approve", {
            method: "POST",
            headers: { Authorization: "Bearer " + token },
        });
        if (!response.ok) {
            throw new Error("Approval failed");
        }
        setPendingApproval(null);
        setMessages((prev) => [
            ...prev,
            {
                id: Date.now().toString(),
                role: "assistant",
                content: `Action approved. ${pendingApproval.tool} → ${pendingApproval.action} is now running.`,
                timestamp: new Date(),
            },
        ]);
    };

    const handleReject = async () => {
        if (!pendingApproval) return;
        const token = await getToken();
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const response = await fetch(apiBase + "/api/agent-runs/" + pendingApproval.run_id + "/reject", {
            method: "POST",
            headers: { Authorization: "Bearer " + token },
        });
        if (!response.ok) {
            throw new Error("Rejection failed");
        }
        setPendingApproval(null);
    };

    const handleApproveWorkflowDraft = async () => {
        if (!pendingWorkflowDraft) return;
        setIsApprovingWorkflowDraft(true);
        setWorkflowDraftError(null);
        try {
            const result = await api<{ workflow_status: string }>(
                `/api/agent-runs/${pendingWorkflowDraft.run_id}/approve-workflow-draft`,
                { method: "POST", body: JSON.stringify({ draft: pendingWorkflowDraft }) },
            );
            const statusLabel = result.workflow_status === "paused" ? "Paused" : "Active";
            setPendingWorkflowDraft(null);
            setMessages((prev) => [
                ...prev,
                {
                    id: Date.now().toString(),
                    role: "assistant",
                    content: `Workflow saved. Status: ${statusLabel}.`,
                    timestamp: new Date(),
                },
            ]);
        } catch (e: unknown) {
            setWorkflowDraftError((e instanceof Error ? e.message : null) ?? "Could not save workflow — please try again.");
        } finally {
            setIsApprovingWorkflowDraft(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const renderToolResult = (tc: ToolCall) => {
        if (tc.status === "pending") {
            return (
                <div className="mt-2 p-2 bg-background/50 rounded flex items-center gap-2 text-xs text-muted-foreground italic border border-border/50">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Using tool <span className="font-semibold text-primary">{tc.tool}</span>...
                </div>
            );
        }

        if (tc.status === "done" && tc.result) {
            try {
                const items = JSON.parse(tc.result) as unknown;
                if (Array.isArray(items) && items.length > 0 && items[0].subject) {
                    return (
                        <div className="mt-3 space-y-2">
                            {(items as EmailResult[]).map((item, idx) => (
                                <EmailCard key={idx} data={item} />
                            ))}
                        </div>
                    );
                }
            } catch {
                // not JSON
            }
            return (
                <div className="mt-2 p-2 bg-accent/30 rounded text-xs text-muted-foreground border border-border/50">
                    ✓ Tool execution successful ({tc.tool})
                </div>
            );
        }
        return null;
    };

    return (
        <div className="h-full flex flex-col bg-chat-bg overflow-hidden rounded-2xl m-3">
            {/* Chat Header */}
            <div className="p-4 border-b border-border flex-shrink-0 flex items-center justify-between">
                <div>
                    <h2 className="font-semibold text-foreground">ByteOps AI</h2>
                    <p className="text-sm text-muted-foreground">AI-enabled workspace</p>
                </div>

                {/* Help popover */}
                <div className="relative" ref={helpRef}>
                    <button
                        onClick={() => setShowHelp(v => !v)}
                        aria-label="What can ByteOps do?"
                        className="text-muted-foreground hover:text-foreground transition-colors p-1.5 rounded-md hover:bg-accent"
                    >
                        <HelpCircle className="w-4 h-4" />
                    </button>

                    {showHelp && (
                        <div className="absolute right-0 top-9 z-50 w-72 rounded-xl border border-border bg-background shadow-lg p-4 text-sm">
                            <p className="font-medium text-foreground mb-3">What can I help you with?</p>
                            {connectedTools.length === 0 ? (
                                <p className="text-muted-foreground">
                                    Connect a tool in Settings → Connections to get started.
                                </p>
                            ) : (
                                <div className="space-y-3 max-h-64 overflow-y-auto custom-scrollbar">
                                    {connectedTools.map(tool => {
                                        const entry = TOOL_CAPABILITIES[tool.tool_type];
                                        if (!entry) return null;
                                        return (
                                            <div key={tool.tool_type}>
                                                <p className="font-medium text-foreground">{entry.label}</p>
                                                <ul className="mt-1 space-y-0.5">
                                                    {entry.capabilities.map(cap => (
                                                        <li key={cap} className="text-muted-foreground">
                                                            · {cap}
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Loading history overlay */}
            {isLoadingHistory && (
                <div className="flex-1 flex items-center justify-center">
                    <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
            )}

            {/* Messages Area */}
            {!isLoadingHistory && (
                <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
                    {/* Messages */}
                    {messages.map((message) => (
                        <div
                            key={message.id}
                            className={cn(
                                "flex gap-3 message-in",
                                message.role === "user" ? "flex-row-reverse" : ""
                            )}
                        >
                            {/* Avatar */}
                            <div
                                className={cn(
                                    "flex items-center justify-center w-8 h-8 rounded-xl flex-shrink-0 mt-1 font-bold text-sm leading-none",
                                    message.role === "user"
                                        ? "bg-primary text-primary-foreground"
                                        : "gradient-ai text-white"
                                )}
                            >
                                {message.role === "user" ? (
                                    <User className="w-4 h-4" />
                                ) : (
                                    <ByteOpsLogoMark className="w-3.5 h-4" />
                                )}
                            </div>

                            {/* Bubble */}
                            <div
                                className={cn(
                                    "max-w-[85%] md:max-w-[75%]",
                                    message.role === "user" ? "items-end" : ""
                                )}
                            >
                                <div
                                    className={cn(
                                        "p-4 rounded-2xl",
                                        message.role === "user"
                                            ? "bg-user-bubble text-foreground"
                                            : "gradient-ai text-white shadow-soft"
                                    )}
                                >
                                    {message.errorClass ? (
                                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                                            <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                                                <AlertCircle size={14} style={{ color: "rgba(255,255,255,0.7)", flexShrink: 0, marginTop: 1 }} />
                                                <span style={{ fontSize: 13, color: "rgba(255,255,255,0.85)", lineHeight: 1.5 }}>
                                                    {CHAT_ERROR_MESSAGES[message.errorClass]?.text ?? CHAT_ERROR_MESSAGES.unknown.text}
                                                </span>
                                            </div>
                                            {CHAT_ERROR_MESSAGES[message.errorClass]?.actionLabel && (
                                                <Link
                                                    href={CHAT_ERROR_MESSAGES[message.errorClass]!.actionPath!}
                                                    style={{
                                                        fontSize: 12,
                                                        color: "rgba(255,255,255,0.9)",
                                                        textDecoration: "underline",
                                                        textUnderlineOffset: 3,
                                                        marginLeft: 22,
                                                    }}
                                                >
                                                    {CHAT_ERROR_MESSAGES[message.errorClass]!.actionLabel}
                                                </Link>
                                            )}
                                        </div>
                                    ) : message.content ? (
                                        <>
                                            {message.role === "user" ? (
                                                <div className="whitespace-pre-wrap text-sm leading-relaxed">
                                                    {message.content}
                                                </div>
                                            ) : (
                                                <div className="text-sm leading-relaxed prose prose-sm prose-invert max-w-none
                                                    [&>p]:mb-2 [&>p:last-child]:mb-0
                                                    [&>ul]:list-disc [&>ul]:pl-4 [&>ul]:mb-2
                                                    [&>ol]:list-decimal [&>ol]:pl-4 [&>ol]:mb-2
                                                    [&>li]:mb-0.5
                                                    [&>h1]:text-base [&>h1]:font-bold [&>h1]:mb-1
                                                    [&>h2]:text-sm [&>h2]:font-semibold [&>h2]:mb-1
                                                    [&>h3]:text-sm [&>h3]:font-medium [&>h3]:mb-1
                                                    [&>code]:bg-white/20 [&>code]:rounded [&>code]:px-1 [&>code]:text-xs
                                                    [&>pre]:bg-black/20 [&>pre]:rounded-lg [&>pre]:p-3 [&>pre]:overflow-x-auto
                                                    [&>pre>code]:bg-transparent [&>pre>code]:px-0
                                                    [&>strong]:font-semibold [&>em]:italic
                                                    [&_code]:bg-white/20 [&_code]:rounded [&_code]:px-1 [&_code]:text-xs
                                                    [&_strong]:font-semibold [&_em]:italic">
                                                    <ReactMarkdown
                                                        components={{
                                                            a: ({ href, children }) => (
                                                                <a
                                                                    href={href}
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className="underline underline-offset-2 opacity-90 hover:opacity-100 break-all"
                                                                >
                                                                    {children}
                                                                </a>
                                                            ),
                                                        }}
                                                    >
                                                        {message.content}
                                                    </ReactMarkdown>
                                                </div>
                                            )}
                                            {message.id === "welcome" && (
                                                <div className="flex flex-wrap gap-2 mt-3">
                                                    {SUGGESTED_PROMPTS.map((prompt, index) => (
                                                        <button
                                                            key={index}
                                                            onClick={() => handleSend(prompt)}
                                                            className="px-3 py-1.5 bg-white/20 hover:bg-white/30 text-white text-sm rounded-full transition-colors border border-white/20 whitespace-nowrap"
                                                        >
                                                            {prompt}
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </>
                                    ) : (
                                        message.role === "assistant" && (
                                            message.stage ? (
                                                <div className="flex items-center gap-2 h-5">
                                                    <div className="w-1.5 h-1.5 bg-white/60 rounded-full animate-pulse" />
                                                    <span style={{ fontSize: 12, color: "rgba(255,255,255,0.75)", fontStyle: "italic" }}>
                                                        {message.stage}
                                                    </span>
                                                </div>
                                            ) : (
                                                (!message.toolCalls || message.toolCalls.length === 0) && (
                                                    <div className="flex gap-1 h-5 items-center">
                                                        <div className="w-1.5 h-1.5 bg-white/70 rounded-full animate-pulse" style={{ animationDelay: "0ms" }} />
                                                        <div className="w-1.5 h-1.5 bg-white/70 rounded-full animate-pulse" style={{ animationDelay: "150ms" }} />
                                                        <div className="w-1.5 h-1.5 bg-white/70 rounded-full animate-pulse" style={{ animationDelay: "300ms" }} />
                                                    </div>
                                                )
                                            )
                                        )
                                    )}

                                    {/* Render tool executions */}
                                    {message.toolCalls?.map((tc, idx) => (
                                        <div key={idx}>{renderToolResult(tc)}</div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    ))}

                    {pendingApproval && (
                        <ApprovalCard
                            approval={pendingApproval}
                            onApprove={handleApprove}
                            onReject={handleReject}
                        />
                    )}

                    {pendingWorkflowDraft && (
                        <WorkflowDraftCard
                            draft={pendingWorkflowDraft}
                            onDraftChange={setPendingWorkflowDraft}
                            onApprove={handleApproveWorkflowDraft}
                            onDismiss={() => { setPendingWorkflowDraft(null); setWorkflowDraftError(null); }}
                            isApproving={isApprovingWorkflowDraft}
                            approveError={workflowDraftError}
                        />
                    )}

                    <div ref={messagesEndRef} />
                </div>
            )}

            {/* Input Area */}
            <div className="border-t border-border p-4 bg-card/50 backdrop-blur-sm rounded-b-2xl flex-shrink-0">
                {/* Attached file chip */}
                {attachedFile && (
                    <div className="flex items-center gap-2 mb-2 px-1">
                        <span className="flex items-center gap-1.5 text-xs bg-accent text-foreground rounded-lg px-2.5 py-1 border border-border">
                            <Paperclip className="w-3 h-3 text-primary" />
                            {attachedFile.name}
                            <button
                                onClick={() => setAttachedFile(null)}
                                className="ml-1 text-muted-foreground hover:text-foreground"
                                aria-label="Remove attachment"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        </span>
                    </div>
                )}
                <div className="flex gap-3 items-end">
                    {/* Hidden file input */}
                    <input
                        ref={fileInputRef}
                        type="file"
                        className="hidden"
                        onChange={(e) => {
                            const file = e.target.files?.[0] ?? null;
                            setAttachedFile(file);
                            e.target.value = "";
                        }}
                    />
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyPress}
                        onInput={(e) => {
                            const el = e.currentTarget;
                            el.style.height = "auto";
                            el.style.height = Math.min(el.scrollHeight, 144) + "px";
                        }}
                        placeholder="Type your message..."
                        className="flex-1 resize-none bg-background border border-border rounded-xl px-4 py-3 focus:ring-2 focus:ring-primary focus:border-transparent outline-none text-sm min-h-[44px] max-h-36"
                        rows={1}
                        disabled={isTyping || isLoadingHistory}
                    />
                    <div className="flex gap-2 pb-2">
                        <button
                            onClick={() => fileInputRef.current?.click()}
                            disabled={isTyping || isLoadingHistory}
                            className="text-muted-foreground hover:text-foreground rounded-xl p-2 transition-colors disabled:opacity-40"
                            aria-label="Attach file"
                        >
                            <Paperclip className="w-5 h-5" />
                        </button>
                        <button className="text-muted-foreground hover:text-foreground rounded-xl p-2 transition-colors">
                            <Mic className="w-5 h-5" />
                        </button>
                        <button
                            onClick={() => handleSend()}
                            disabled={(!input.trim() && !attachedFile) || isTyping || isLoadingHistory}
                            className="gradient-primary hover:shadow-glow p-2 rounded-xl text-primary-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-shadow"
                        >
                            {isTyping ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                                <Send className="w-4 h-4" />
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
