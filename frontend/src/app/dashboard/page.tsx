"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Panel, Group, Separator, usePanelRef } from "react-resizable-panels";
import { TopBar } from "@/components/dashboard/top-bar";
import { CollapsibleSidebar } from "@/components/dashboard/collapsible-sidebar";
import { ChatInterface } from "@/components/dashboard/chat-interface";
import { ContextPanel } from "@/components/dashboard/context-panel";
import { useConversations } from "@/hooks/use-conversations";

export default function DashboardPage() {
    const searchParams = useSearchParams();
    const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
    const [isRightCollapsed, setIsRightCollapsed] = useState(false);
    const contextPanelRef = usePanelRef();

    // ── Shared conversation state ─────────────────────────────────────────────
    const [activeConversationId, setActiveConversationId] = useState<string | null>(
        searchParams.get("conversation")
    );
    // chatKey: incremented on every "New Chat" click to force ChatInterface remount,
    // which resets all local state (messages, input, isTyping) even when
    // activeConversationId is already null (null→null wouldn't trigger useEffect).
    const [chatKey, setChatKey] = useState(0);
    const { conversations, isLoading, refresh, deleteConversation, renameConversation } =
        useConversations();

    // If navigated from another page with ?conversation=<id>, open that thread
    useEffect(() => {
        const id = searchParams.get("conversation");
        if (id) setActiveConversationId(id);
    }, [searchParams]);

    // Ref to the ContextPanel's refresh function — populated by the panel itself
    const contextRefreshRef = useRef<(() => void) | null>(null);

    // ── Ask AI bridge: notification → chat input ──────────────────────────────
    const [pendingMessage, setPendingMessage] = useState<string | null>(null);
    const handleSendToAI = useCallback((message: string) => {
        setPendingMessage(message);
    }, []);
    const clearPendingMessage = useCallback(() => setPendingMessage(null), []);

    /** Called by ChatInterface when a new conversation is created via the first message. */
    const handleConversationCreated = useCallback(
        (id: string) => {
            setActiveConversationId(id);
            refresh(); // pull new conversation into sidebar list
            contextRefreshRef.current?.(); // surface new agent notifications and workflows immediately
        },
        [refresh]
    );

    const handleWorkflowSaved = useCallback(() => {
        contextRefreshRef.current?.();
    }, []);

    /** Called by the sidebar "New Chat" button.
     *  Always increments chatKey so ChatInterface fully remounts — this works
     *  even when activeConversationId is already null (null→null = no React
     *  state diff, so without the key the component would not reset). */
    const handleNewChat = useCallback(() => {
        setActiveConversationId(null);
        setChatKey((k) => k + 1);
    }, []);

    /** Called by the sidebar when user clicks a historical conversation. */
    const handleSelectConversation = useCallback((id: string) => {
        setActiveConversationId(id);
    }, []);

    const handleCollapseRight = () => {
        if (isRightCollapsed) {
            contextPanelRef.current?.expand();
            setIsRightCollapsed(false);
        } else {
            contextPanelRef.current?.collapse();
            setIsRightCollapsed(true);
        }
    };

    return (
        <div className="h-screen flex flex-col bg-background overflow-hidden">
            <TopBar />

            {/* Main 3-panel area */}
            <div className="flex flex-1 overflow-hidden">

                {/* ── Left Sidebar ───────────────────────────────────────────── */}
                <div
                    className="flex-shrink-0 overflow-hidden transition-[width] duration-300 ease-in-out"
                    style={{ width: isLeftCollapsed ? 64 : 256 }}
                >
                    <div className="h-full" style={{ width: isLeftCollapsed ? 64 : 256 }}>
                        <CollapsibleSidebar
                            isCollapsed={isLeftCollapsed}
                            onToggleCollapse={() => setIsLeftCollapsed((v) => !v)}
                            conversations={conversations}
                            isLoadingConversations={isLoading}
                            activeConversationId={activeConversationId}
                            onNewChat={handleNewChat}
                            onSelectConversation={handleSelectConversation}
                            onDeleteConversation={deleteConversation}
                            onRenameConversation={renameConversation}
                        />
                    </div>
                </div>

                {/* ── Center + Right: resizable ───────────────────────────────── */}
                <Group
                    orientation="horizontal"
                    className="flex-1 overflow-hidden"
                    defaultLayout={{ chat: 65, context: 35 }}
                >
                    {/* Chat Panel */}
                    <Panel id="chat" minSize="30%">
                        <div className="h-full overflow-hidden">
                            <ChatInterface
                                key={chatKey}
                                conversationId={activeConversationId}
                                onConversationCreated={handleConversationCreated}
                                onWorkflowSaved={handleWorkflowSaved}
                                initialMessage={pendingMessage}
                                onInitialMessageConsumed={clearPendingMessage}
                            />
                        </div>
                    </Panel>

                    {/* Resize handle */}
                    <Separator
                        className="w-1 flex-shrink-0 cursor-col-resize transition-colors"
                        style={{ background: "var(--border)" }}
                    />

                    {/* Context Panel */}
                    <Panel
                        id="context"
                        panelRef={contextPanelRef}
                        collapsible
                        collapsedSize="64px"
                        defaultSize="35%"
                        minSize="20%"
                        maxSize="45%"
                    >
                        <div className="h-full overflow-hidden">
                            <ContextPanel
                                isCollapsed={isRightCollapsed}
                                onToggleCollapse={handleCollapseRight}
                                onRefreshRef={contextRefreshRef}
                                onSendToAI={handleSendToAI}
                            />
                        </div>
                    </Panel>
                </Group>
            </div>
        </div>
    );
}
