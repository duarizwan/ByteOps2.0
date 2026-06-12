"use client";

import { useAuth } from "@clerk/nextjs";
import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
    type ReactNode,
} from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ToolType =
    | "gmail"
    | "github"
    | "jira"
    | "slack"
    | "trello"
    | "dropbox"
    | "calendar";

export interface ToolConnection {
    id: string;
    tool_type: ToolType;
    status: "connected" | "disconnected" | "expired" | "error";
    scopes: string | null;
    connected_at: string;
}

interface ToolConnectionsContextValue {
    connections: ToolConnection[];
    loading: boolean;
    error: string | null;
    isConnected: (tool: ToolType) => boolean;
    initiateConnect: (tool: ToolType) => Promise<void>;
    disconnect: (tool: ToolType) => Promise<void>;
    silentRefresh: (tool: ToolType) => Promise<{ refreshed: boolean; error?: string }>;
    refetch: () => Promise<void>;
    connectViaApiKey: (tool: ToolType, credentials: Record<string, string>) => Promise<void>;
}

const ToolConnectionsContext = createContext<ToolConnectionsContextValue | null>(null);

export function ToolConnectionsProvider({ children }: { children: ReactNode }) {
    const { getToken } = useAuth();
    const [connections, setConnections] = useState<ToolConnection[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const inflightRef = useRef<Promise<void> | null>(null);

    const fetchConnections = useCallback(async () => {
        if (inflightRef.current) {
            return inflightRef.current;
        }

        const run = (async () => {
            setError(null);
            try {
                const token = await getToken();
                if (!token) {
                    setConnections([]);
                    return;
                }

                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 5000);

                const res = await fetch(`${API_BASE}/api/tools/connections`, {
                    headers: { Authorization: `Bearer ${token}` },
                    signal: controller.signal,
                });
                clearTimeout(timeoutId);

                if (!res.ok) {
                    const body = await res.text().catch(() => "");
                    throw new Error(`Backend returned ${res.status}: ${body.slice(0, 100)}`);
                }
                setConnections(await res.json());
            } catch (e) {
                if (e instanceof DOMException && e.name === "AbortError") {
                    setError("Backend timed out — is it running?");
                } else if (e instanceof TypeError && (e.message.includes("fetch") || e.message.includes("Failed"))) {
                    setError("Cannot reach backend at " + API_BASE);
                } else {
                    setError(e instanceof Error ? e.message : "Unknown error");
                }
            } finally {
                setLoading(false);
            }
        })();

        inflightRef.current = run;
        try {
            await run;
        } finally {
            inflightRef.current = null;
        }
    }, [getToken]);

    useEffect(() => {
        fetchConnections();
    }, [fetchConnections]);

    const initiateConnect = useCallback(
        async (tool: ToolType) => {
            const token = await getToken();
            if (!token) {
                throw new Error("You must be signed in to connect tools");
            }

            let res = await fetch(`${API_BASE}/api/auth/${tool}/initiate`, {
                headers: { Authorization: `Bearer ${token}` },
            });

            if (res.status === 401) {
                const freshToken = await getToken({ skipCache: true });
                if (freshToken) {
                    res = await fetch(`${API_BASE}/api/auth/${tool}/initiate`, {
                        headers: { Authorization: `Bearer ${freshToken}` },
                    });
                }
            }

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail ?? `Failed to initiate ${tool} auth`);
            }
            const { auth_url } = await res.json();
            window.location.href = auth_url;
        },
        [getToken]
    );

    const silentRefresh = useCallback(
        async (tool: ToolType): Promise<{ refreshed: boolean; error?: string }> => {
            const token = await getToken();
            if (!token) return { refreshed: false, error: "Not signed in" };
            const res = await fetch(`${API_BASE}/api/auth/${tool}/refresh`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                return { refreshed: false, error: err.detail ?? "Refresh failed" };
            }
            await fetchConnections();
            return { refreshed: true };
        },
        [getToken, fetchConnections]
    );

    const disconnect = useCallback(
        async (tool: ToolType) => {
            const token = await getToken();
            if (!token) {
                throw new Error("You must be signed in to disconnect tools");
            }
            const res = await fetch(`${API_BASE}/api/auth/${tool}/disconnect`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!res.ok) throw new Error(`Failed to disconnect ${tool}`);
            await fetchConnections();
        },
        [getToken, fetchConnections]
    );

    const connectViaApiKey = useCallback(
        async (tool: ToolType, credentials: Record<string, string>) => {
            const token = await getToken();
            if (!token) throw new Error("You must be signed in to connect tools");
            const res = await fetch(`${API_BASE}/api/auth/${tool}/connect-apikey`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ credentials }),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail ?? `Failed to connect ${tool}`);
            }
            await fetchConnections();
        },
        [getToken, fetchConnections]
    );

    const isConnected = useCallback(
        (tool: ToolType) => connections.some((c) => c.tool_type === tool && c.status === "connected"),
        [connections]
    );

    const value = useMemo(
        () => ({
            connections,
            loading,
            error,
            isConnected,
            initiateConnect,
            disconnect,
            silentRefresh,
            refetch: fetchConnections,
            connectViaApiKey,
        }),
        [
            connections,
            loading,
            error,
            isConnected,
            initiateConnect,
            disconnect,
            silentRefresh,
            fetchConnections,
            connectViaApiKey,
        ]
    );

    return (
        <ToolConnectionsContext.Provider value={value}>
            {children}
        </ToolConnectionsContext.Provider>
    );
}

export function useToolConnections(): ToolConnectionsContextValue {
    const ctx = useContext(ToolConnectionsContext);
    if (!ctx) {
        throw new Error("useToolConnections must be used within ToolConnectionsProvider");
    }
    return ctx;
}
