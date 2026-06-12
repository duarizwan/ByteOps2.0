/**
 * useConversations — manages the user's conversation list.
 *
 * Fetches all conversations on mount, exposes mutation helpers (createNew,
 * deleteConversation, renameConversation), and refreshes the list after each
 * mutation so the sidebar stays in sync.
 *
 * Uses useAuth().getToken() (the proper Clerk React hook) instead of
 * window.Clerk.session.getToken() to avoid race conditions on first render
 * where Clerk's session may not yet be available via the window global.
 */
"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";

export interface ConversationSummary {
    id: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
}

export interface ConversationMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    created_at: string;
}

export interface ConversationDetail extends ConversationSummary {
    messages: ConversationMessage[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/* ── Conversation detail cache ───────────────────────────────────────────────
   Module-level cache so the cache survives across component remounts.
   Each entry expires after CACHE_TTL_MS. The cache is invalidated on delete
   and rename so stale data is never shown after mutations.
   ──────────────────────────────────────────────────────────────────────────── */
const CACHE_TTL_MS = 60_000; // 60 seconds

interface CacheEntry {
    data: ConversationDetail;
    expiresAt: number;
}

const detailCache = new Map<string, CacheEntry>();

function getCached(id: string): ConversationDetail | null {
    const entry = detailCache.get(id);
    if (!entry) return null;
    if (Date.now() > entry.expiresAt) {
        detailCache.delete(id);
        return null;
    }
    return entry.data;
}

function setCached(id: string, data: ConversationDetail): void {
    detailCache.set(id, { data, expiresAt: Date.now() + CACHE_TTL_MS });
}

/**
 * Shared fetch helper — accepts the Clerk getToken function from useAuth()
 * so it always uses the correct, fresh token for the current Clerk session.
 */
async function authFetch(
    path: string,
    getToken: () => Promise<string | null>,
    init: RequestInit = {}
): Promise<Response> {
    const token = await getToken();
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(init.headers as Record<string, string>),
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(`${API_BASE}${path}`, { ...init, headers });
}

export function useConversations() {
    // useAuth().getToken() is the correct Clerk pattern — it waits for Clerk to
    // be fully initialized and returns a fresh JWT for the active session.
    // This replaces the fragile window.Clerk.session.getToken() approach.
    const { getToken } = useAuth();
    const [conversations, setConversations] = useState<ConversationSummary[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const refresh = useCallback(async () => {
        setIsLoading(true);
        try {
            const res = await authFetch("/api/chat/conversations", getToken);
            if (res.ok) {
                const data: ConversationSummary[] = await res.json();
                setConversations(data);
            }
        } catch (e) {
            console.error("Failed to fetch conversations:", e);
        } finally {
            setIsLoading(false);
        }
    }, [getToken]);

    useEffect(() => {
        refresh();
    }, [refresh]);

    /** Delete a conversation by ID. Returns true on success. */
    const deleteConversation = useCallback(async (id: string): Promise<boolean> => {
        try {
            const res = await authFetch(
                `/api/chat/conversations/${id}`,
                getToken,
                { method: "DELETE" }
            );
            if (res.ok || res.status === 204) {
                setConversations((prev) => prev.filter((c) => c.id !== id));
                detailCache.delete(id); // Invalidate cache entry
                return true;
            }
        } catch (e) {
            console.error("Failed to delete conversation:", e);
        }
        return false;
    }, [getToken]);

    /** Rename a conversation. Returns the updated summary or null on failure. */
    const renameConversation = useCallback(
        async (id: string, title: string): Promise<ConversationSummary | null> => {
            try {
                const res = await authFetch(
                    `/api/chat/conversations/${id}`,
                    getToken,
                    { method: "PATCH", body: JSON.stringify({ title }) }
                );
                if (res.ok) {
                    const updated: ConversationSummary = await res.json();
                    setConversations((prev) =>
                        prev.map((c) => (c.id === updated.id ? updated : c))
                    );
                    detailCache.delete(id); // Invalidate so next fetch gets fresh title
                    return updated;
                }
            } catch (e) {
                console.error("Failed to rename conversation:", e);
            }
            return null;
        },
        [getToken]
    );

    /** Fetch a conversation's full message history. Returns from cache if fresh. */
    const getConversationDetail = useCallback(
        async (id: string): Promise<ConversationDetail | null> => {
            // Return cached data if it's still fresh — avoids API round-trip on quick switches
            const cached = getCached(id);
            if (cached) return cached;

            try {
                const res = await authFetch(`/api/chat/conversations/${id}`, getToken);
                if (res.ok) {
                    const data: ConversationDetail = await res.json();
                    setCached(id, data);
                    return data;
                }
            } catch (e) {
                console.error("Failed to load conversation:", e);
            }
            return null;
        },
        [getToken]
    );

    return {
        conversations,
        isLoading,
        refresh,
        deleteConversation,
        renameConversation,
        getConversationDetail,
    };
}
