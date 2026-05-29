/**
 * useNotifications — fetches and manages the activity feed.
 *
 * Polls every 30 seconds and exposes mutation helpers.
 * Errors are silently swallowed so the UI never crashes the page.
 *
 * Uses useAuth().getToken() (proper Clerk React hook) so that the token is
 * always valid for the current session — avoids the window.Clerk.session race
 * condition that causes 401 errors on first render.
 */
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@clerk/nextjs";

export interface Notification {
    id: string;
    source_tool: string;
    title: string;
    content: string | null;
    priority: "low" | "medium" | "high" | "urgent";
    is_read: boolean;
    created_at: string;
    metadata?: Record<string, unknown>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const POLL_INTERVAL_MS = 30_000;

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

export function useNotifications() {
    const { getToken } = useAuth();
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetch_ = useCallback(async (silent = false) => {
        if (!silent) setIsLoading(true);
        try {
            const res = await authFetch("/api/notifications", getToken);
            if (res.ok) {
                const data: Notification[] = await res.json();
                setNotifications(data);
            }
        } catch {
            // Network error — keep stale data, don't crash
        } finally {
            if (!silent) setIsLoading(false);
        }
    }, [getToken]);

    // Initial fetch + polling
    useEffect(() => {
        fetch_();
        intervalRef.current = setInterval(() => fetch_(true), POLL_INTERVAL_MS);
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [fetch_]);

    const refresh = useCallback(() => fetch_(), [fetch_]);

    const unreadCount = notifications.filter((n) => !n.is_read).length;

    /** Mark a single notification as read (optimistic update). */
    const markRead = useCallback(async (id: string) => {
        setNotifications((prev) =>
            prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
        );
        try {
            await authFetch(`/api/notifications/${id}/read`, getToken, { method: "PATCH" });
        } catch {
            await fetch_(true);
        }
    }, [getToken, fetch_]);

    /** Mark all notifications as read (optimistic update). */
    const markAllRead = useCallback(async () => {
        setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
        try {
            await authFetch("/api/notifications/read-all", getToken, { method: "POST" });
        } catch {
            await fetch_(true);
        }
    }, [getToken, fetch_]);

    /** Dismiss (delete) a notification (optimistic update). */
    const dismiss = useCallback(async (id: string) => {
        setNotifications((prev) => prev.filter((n) => n.id !== id));
        try {
            await authFetch(`/api/notifications/${id}`, getToken, { method: "DELETE" });
        } catch {
            await fetch_(true);
        }
    }, [getToken, fetch_]);

    return {
        notifications,
        unreadCount,
        isLoading,
        refresh,
        markRead,
        markAllRead,
        dismiss,
    };
}
