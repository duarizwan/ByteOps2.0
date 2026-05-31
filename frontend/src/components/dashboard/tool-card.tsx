"use client";

import { useState } from "react";
import { Check, RefreshCw, X, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ToolType } from "@/hooks/use-tool-connections";
import { getBrandIconUrl } from "@/lib/brand-icons";

const SILENT_REFRESH_TOOLS: ToolType[] = ["gmail", "calendar"];

interface ToolMeta {
    id: ToolType;
    name: string;
    description: string;
}

interface ToolCardProps {
    tool: ToolMeta;
    isConnected: boolean;
    onConnect: (tool: ToolType) => void;
    onDisconnect: (tool: ToolType) => Promise<void>;
    onSilentRefresh?: (tool: ToolType) => Promise<{ refreshed: boolean; error?: string }>;
}

export function ToolCard({ tool, isConnected, onConnect, onDisconnect, onSilentRefresh }: ToolCardProps) {
    const [refreshing, setRefreshing] = useState(false);
    const [refreshMsg, setRefreshMsg] = useState<string | null>(null);

    const canSilentRefresh = SILENT_REFRESH_TOOLS.includes(tool.id) && !!onSilentRefresh;

    async function handleSilentRefresh() {
        if (!onSilentRefresh) return;
        setRefreshing(true);
        setRefreshMsg(null);
        const result = await onSilentRefresh(tool.id);
        setRefreshing(false);
        setRefreshMsg(result.refreshed ? "Token refreshed" : (result.error ?? "Failed"));
        setTimeout(() => setRefreshMsg(null), 3000);
    }
    return (
        <div
            className={cn(
                "bg-card rounded-2xl p-5 hover:shadow-medium transition-all duration-200 flex flex-col gap-4 border overflow-hidden relative",
                isConnected ? "border-primary/30" : "border-border"
            )}
        >
            {/* Left accent bar for connected state */}
            {isConnected && (
                <div className="absolute inset-y-0 left-0 w-1 bg-primary rounded-l-2xl" />
            )}

            {/* Header */}
            <div className="flex items-start justify-between pl-1">
                <div className="w-11 h-11 rounded-xl flex items-center justify-center bg-accent overflow-hidden">
                    {(() => {
                        const url = getBrandIconUrl(tool.id);
                        return url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={url} alt={tool.name} width={28} height={28} className="object-contain" />
                        ) : (
                            <span className="text-sm font-bold text-muted-foreground">{tool.name[0]}</span>
                        );
                    })()}
                </div>
                {isConnected ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-xs font-medium">
                        <Check className="w-3 h-3" />
                        Connected
                    </span>
                ) : (
                    <span className="inline-flex items-center px-2.5 py-1 rounded-xl bg-muted text-muted-foreground text-xs font-medium">
                        Not Connected
                    </span>
                )}
            </div>

            {/* Info */}
            <div className="pl-1">
                <h3 className="font-semibold mb-1">{tool.name}</h3>
                <p className="text-sm text-muted-foreground">{tool.description}</p>
            </div>

            {/* Actions */}
            <div className="flex flex-col gap-2 mt-auto pl-1">
                {refreshMsg && (
                    <p className={cn("text-xs", refreshMsg === "Token refreshed" ? "text-green-600 dark:text-green-400" : "text-destructive")}>
                        {refreshMsg}
                    </p>
                )}
                <div className="flex gap-2">
                {isConnected ? (
                    <>
                        {canSilentRefresh && (
                            <button
                                onClick={handleSilentRefresh}
                                disabled={refreshing}
                                className="flex items-center justify-center gap-1.5 px-3 py-2 text-sm rounded-xl border border-primary/40 text-primary bg-primary/5 hover:bg-primary/10 transition-colors disabled:opacity-50"
                            >
                                <Zap className="w-3.5 h-3.5" />
                                {refreshing ? "Refreshing…" : "Refresh Token"}
                            </button>
                        )}
                        <button
                            onClick={() => onConnect(tool.id)}
                            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm rounded-xl border border-border bg-background hover:bg-accent transition-colors"
                        >
                            <RefreshCw className="w-3.5 h-3.5" />
                            Reconnect
                        </button>
                        <button
                            onClick={() => onDisconnect(tool.id)}
                            className="flex items-center justify-center px-3 py-2 text-sm rounded-xl bg-destructive/10 text-destructive hover:bg-destructive hover:text-white transition-colors"
                        >
                            <X className="w-3.5 h-3.5" />
                        </button>
                    </>
                ) : (
                    <button
                        onClick={() => onConnect(tool.id)}
                        className="w-full px-3 py-2 text-sm rounded-xl gradient-primary text-white hover:shadow-glow transition-all"
                    >
                        Connect
                    </button>
                )}
                </div>
            </div>
        </div>
    );
}

export type { ToolMeta };
