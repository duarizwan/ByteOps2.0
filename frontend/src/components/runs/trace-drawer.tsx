"use client";

import { useState, useEffect } from "react";
import { ArrowLeft, Zap } from "lucide-react";
import type { AgentRun } from "@/hooks/use-agent-runs";
import { summarizeAction } from "@/lib/summarize-action";
import { GraphCanvas } from "./graph-canvas";

interface TraceDrawerProps {
    run: AgentRun | null;
    onClose: () => void;
}

export function TraceDrawer({ run, onClose }: TraceDrawerProps) {
    const [isGraphReady, setIsGraphReady] = useState(false);

    useEffect(() => {
        setIsGraphReady(false);
    }, [run?.id]);

    if (!run) return null;

    const { summary } = summarizeAction(run);

    return (
        <div
            data-drawer
            data-open="true"
            style={{
                position: "fixed",
                inset: 0,
                zIndex: 50,
                display: "flex",
                flexDirection: "column",
                background: "var(--background)",
            }}
        >
            {/* Header */}
            <div style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "9px 16px",
                borderBottom: "1px solid var(--border)",
                background: "var(--background)",
                flexShrink: 0,
            }}>
                <button
                    aria-label="Back to Action Center"
                    onClick={onClose}
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        padding: "5px 12px",
                        borderRadius: 8,
                        border: "1px solid var(--border)",
                        background: "var(--card)",
                        color: "var(--muted-foreground)",
                        fontSize: 12,
                        fontWeight: 500,
                        cursor: "pointer",
                        transition: "border-color 0.15s, color 0.15s",
                        flexShrink: 0,
                    }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = "var(--primary)";
                        e.currentTarget.style.color = "var(--primary)";
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = "var(--border)";
                        e.currentTarget.style.color = "var(--muted-foreground)";
                    }}
                >
                    <ArrowLeft size={13} />
                    Action Center
                </button>

                <div style={{ width: 1, height: 16, background: "var(--border)" }} />

                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <Zap size={14} style={{ color: "var(--primary)" }} />
                    <span style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "var(--foreground)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    }}>
                        {summary}
                    </span>
                </div>
            </div>

            {/* Full-screen graph */}
            <div style={{ flex: 1, overflow: "hidden", position: "relative" }}>
                {!isGraphReady && (
                    <div
                        style={{
                            position: "absolute",
                            inset: 0,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            background: "var(--background)",
                            zIndex: 1,
                        }}
                    >
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                            <div style={{
                                width: 32,
                                height: 32,
                                border: "2px solid var(--border)",
                                borderTop: "2px solid var(--primary)",
                                borderRadius: "50%",
                            }} className="animate-spin" />
                            <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>Loading trace…</span>
                        </div>
                    </div>
                )}
                <GraphCanvas
                    selectedRunId={run.id}
                    onLoad={() => setIsGraphReady(true)}
                />
            </div>
        </div>
    );
}
