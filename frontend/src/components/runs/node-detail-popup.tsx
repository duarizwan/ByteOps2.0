"use client";

import { useState } from "react";
import { X, ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import {
    MessageCircle, GitBranch, FileText, Wrench,
    Server, ShieldCheck, CheckCircle2, Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { GraphNode, GraphNodeType } from "@/lib/graph-transformer";
import { TYPE_COLOR, TYPE_LABEL_COLOR } from "@/lib/graph-transformer";

const ICONS: Record<GraphNodeType, LucideIcon> = {
    user_input:     MessageCircle,
    intent_router:  GitBranch,
    agent_plan:     FileText,
    tool_call:      Wrench,
    platform_api:   Server,
    approval_gate:  ShieldCheck,
    verify:         CheckCircle2,
    final_response: Sparkles,
};

const STATUS_COLOR: Record<string, string> = {
    completed: "#22C55E",
    failed:    "#EF4444",
    running:   "#3B82F6",
    pending:   "#F59E0B",
    approved:  "#22C55E",
    awaiting:  "#F59E0B",
    ok:        "#22C55E",
    error:     "#EF4444",
};

const RISK_COLOR: Record<string, string> = {
    READ:          "#3B82F6",
    WRITE:         "#F59E0B",
    DESTRUCTIVE:   "#EF4444",
    EXTERNAL_SEND: "#A855F7",
    NONE:          "#475569",
};

function prettyKey(k: string): string {
    return k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function ValueDisplay({ value }: { value: unknown }) {
    const [expanded, setExpanded] = useState(false);

    if (value === null || value === undefined) {
        return <span style={{ color: "var(--muted-foreground)", fontStyle: "italic" }}>—</span>;
    }
    if (typeof value === "boolean") {
        return (
            <span style={{
                padding: "1px 7px", borderRadius: 4, fontSize: 10.5, fontWeight: 600,
                background: value
                    ? "rgba(34, 197, 94, 0.12)"
                    : "rgba(239, 68, 68, 0.12)",
                color: value ? "#16A34A" : "#DC2626",
                border: `1px solid ${value ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
            }}>
                {value ? "true" : "false"}
            </span>
        );
    }
    if (typeof value === "number") {
        return <span style={{ color: "var(--primary)", fontWeight: 500 }}>{value}</span>;
    }
    if (typeof value === "string") {
        const isLong = value.length > 100;
        const display = isLong && !expanded ? value.slice(0, 100) : value;
        return (
            <span>
                <span style={{ color: "var(--foreground)", wordBreak: "break-word" }}>{display}</span>
                {isLong && (
                    <button
                        onClick={() => setExpanded((v) => !v)}
                        style={{ marginLeft: 4, fontSize: 10, color: "var(--primary)", background: "none", border: "none", cursor: "pointer", padding: 0 }}
                    >
                        {expanded ? "less" : `+${value.length - 100} more`}
                    </button>
                )}
            </span>
        );
    }
    if (Array.isArray(value)) {
        if (value.length === 0) return <span style={{ color: "var(--muted-foreground)", fontStyle: "italic" }}>empty list</span>;
        return (
            <div>
                <button
                    onClick={() => setExpanded((v) => !v)}
                    style={{ display: "flex", alignItems: "center", gap: 4, background: "none", border: "none", cursor: "pointer", padding: 0, color: "var(--muted-foreground)" }}
                >
                    {expanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                    <span style={{ fontSize: 11 }}>{value.length} item{value.length !== 1 ? "s" : ""}</span>
                </button>
                {expanded && (
                    <div style={{ marginTop: 4, paddingLeft: 12, borderLeft: "1px solid var(--border)" }}>
                        {value.slice(0, 8).map((item, i) => (
                            <div key={i} style={{ fontSize: 11, color: "var(--foreground)", padding: "2px 0" }}>
                                <span style={{ color: "var(--muted-foreground)", marginRight: 6 }}>[{i}]</span>
                                <ValueDisplay value={item} />
                            </div>
                        ))}
                        {value.length > 8 && (
                            <div style={{ fontSize: 10.5, color: "var(--muted-foreground)", paddingTop: 2 }}>
                                +{value.length - 8} more…
                            </div>
                        )}
                    </div>
                )}
            </div>
        );
    }
    if (typeof value === "object") {
        const entries = Object.entries(value as Record<string, unknown>);
        if (entries.length === 0) return <span style={{ color: "var(--muted-foreground)", fontStyle: "italic" }}>{"{}"}</span>;
        return (
            <div>
                <button
                    onClick={() => setExpanded((v) => !v)}
                    style={{ display: "flex", alignItems: "center", gap: 4, background: "none", border: "none", cursor: "pointer", padding: 0, color: "var(--muted-foreground)" }}
                >
                    {expanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                    <span style={{ fontSize: 11 }}>{expanded ? "collapse" : `{${entries.length} fields}`}</span>
                </button>
                {expanded && (
                    <div style={{ marginTop: 4, paddingLeft: 12, borderLeft: "1px solid var(--border)" }}>
                        {entries.map(([k, v]) => (
                            <div key={k} style={{ fontSize: 11, color: "var(--foreground)", padding: "2px 0", display: "flex", gap: 6, alignItems: "flex-start" }}>
                                <span style={{ color: "var(--muted-foreground)", flexShrink: 0 }}>{k}:</span>
                                <ValueDisplay value={v} />
                            </div>
                        ))}
                    </div>
                )}
            </div>
        );
    }
    return <span style={{ color: "var(--foreground)" }}>{String(value)}</span>;
}

const PAYLOAD_CHAR_LIMIT = 500;

function TruncatedPayload({ data }: { data: Record<string, unknown> }) {
    const [showFull, setShowFull] = useState(false);
    const json = JSON.stringify(data, null, 2);
    const isLarge = json.length > PAYLOAD_CHAR_LIMIT;

    if (!isLarge || showFull) return <PayloadTable data={data} />;

    return (
        <div>
            <pre style={{
                fontSize: 11, color: "var(--foreground)", background: "var(--muted)",
                borderRadius: 6, padding: "8px 10px", overflowX: "auto",
                margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word",
                lineHeight: 1.5, maxHeight: 120, overflow: "hidden",
                borderBottom: "1px solid var(--border)",
            }}>
                {json.slice(0, PAYLOAD_CHAR_LIMIT)}…
            </pre>
            <button
                onClick={() => setShowFull(true)}
                style={{
                    marginTop: 6, fontSize: 11, color: "var(--primary)",
                    background: "none", border: "none", cursor: "pointer", padding: 0,
                }}
            >
                Show full ({json.length} chars)
            </button>
        </div>
    );
}

function PayloadTable({ data }: { data: Record<string, unknown> }) {
    const entries = Object.entries(data);
    if (entries.length === 0) return (
        <p style={{ fontSize: 11.5, color: "var(--muted-foreground)", fontStyle: "italic" }}>No data</p>
    );
    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {entries.map(([k, v]) => (
                <div key={k} style={{
                    display: "grid",
                    gridTemplateColumns: "90px 1fr",
                    gap: 8,
                    alignItems: "start",
                    padding: "5px 0",
                    borderBottom: "1px solid var(--border)",
                }}>
                    <span style={{
                        fontSize: 10.5, fontWeight: 600, color: "var(--muted-foreground)",
                        textTransform: "uppercase", letterSpacing: "0.04em",
                        paddingTop: 2, wordBreak: "break-word",
                    }}>
                        {prettyKey(k)}
                    </span>
                    <span style={{ fontSize: 12 }}>
                        <ValueDisplay value={v} />
                    </span>
                </div>
            ))}
        </div>
    );
}

interface NodeDetailPopupProps {
    node: GraphNode;
    onClose: () => void;
}

export function NodeDetailPopup({ node, onClose }: NodeDetailPopupProps) {
    const d = node.data;
    const Icon = ICONS[d.nodeType] ?? Wrench;
    const isFailed = d.status === "failed";
    const borderColor = isFailed ? "#EF4444" : TYPE_COLOR[d.nodeType];
    const labelColor = isFailed ? "#FCA5A5" : TYPE_LABEL_COLOR[d.nodeType];
    const statusColor = STATUS_COLOR[d.status] ?? "#475569";
    const riskColor = RISK_COLOR[d.riskLevel] ?? "#475569";

    return (
        <div style={{
            position: "absolute",
            top: 16,
            right: 16,
            zIndex: 100,
            width: 340,
            maxHeight: "calc(100% - 32px)",
            overflowY: "auto",
            background: "var(--popover)",
            border: `1px solid ${borderColor}30`,
            borderRadius: 16,
            boxShadow: `0 0 0 1px ${borderColor}12, 0 32px 64px rgba(0,0,0,0.25), 0 0 40px ${borderColor}0A`,
            display: "flex",
            flexDirection: "column",
        }}>
            {/* Top accent glow line */}
            <div style={{
                position: "absolute",
                top: 0, left: "20%", right: "20%", height: 1,
                background: `linear-gradient(90deg, transparent, ${borderColor}70, transparent)`,
                borderRadius: "0 0 4px 4px",
            }} />

            {/* Header */}
            <div style={{ padding: "16px 16px 10px", display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                    <div style={{
                        width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                        background: `${borderColor}15`,
                        border: `1px solid ${borderColor}35`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                        <Icon size={16} color={labelColor} strokeWidth={1.5} />
                    </div>
                    <div style={{ minWidth: 0 }}>
                        <div style={{
                            fontSize: 14, fontWeight: 700, color: "var(--foreground)",
                            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        }}>
                            {d.label}
                        </div>
                        <div style={{ fontSize: 10.5, color: "var(--muted-foreground)", marginTop: 1 }}>
                            {d.nodeType.replace(/_/g, " ")}
                        </div>
                    </div>
                </div>
                <button
                    onClick={onClose}
                    aria-label="Close"
                    style={{
                        flexShrink: 0,
                        width: 26, height: 26,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        background: "none", border: "1px solid var(--border)",
                        borderRadius: 7, cursor: "pointer", color: "var(--muted-foreground)",
                        transition: "border-color 0.15s, color 0.15s",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#EF4444"; e.currentTarget.style.color = "#EF4444"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--muted-foreground)"; }}
                >
                    <X size={13} />
                </button>
            </div>

            {/* Status + risk + duration pills */}
            <div style={{ padding: "0 16px 12px", display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span style={{
                    display: "inline-flex", alignItems: "center", gap: 4,
                    padding: "3px 9px", borderRadius: 999, fontSize: 11, fontWeight: 500,
                    background: `${statusColor}15`, border: `1px solid ${statusColor}35`, color: statusColor,
                }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: statusColor, display: "inline-block" }} />
                    {d.status}
                </span>
                {d.riskLevel !== "NONE" && (
                    <span style={{
                        display: "inline-flex", alignItems: "center", gap: 4,
                        padding: "3px 9px", borderRadius: 999, fontSize: 11, fontWeight: 500,
                        background: `${riskColor}10`, border: `1px solid ${riskColor}30`, color: riskColor,
                    }}>
                        {d.riskLevel}
                    </span>
                )}
                {d.durationMs !== null && d.durationMs !== undefined && (
                    <span style={{
                        display: "inline-flex", alignItems: "center", gap: 4,
                        padding: "3px 9px", borderRadius: 999, fontSize: 11, fontWeight: 500,
                        background: "var(--muted)", border: "1px solid var(--border)", color: "var(--muted-foreground)",
                    }}>
                        {d.durationMs}ms
                    </span>
                )}
            </div>

            {/* Input section */}
            {d.input && Object.keys(d.input).length > 0 && (
                <>
                    <div style={{ height: 1, background: "var(--border)", margin: "0 16px" }} />
                    <div style={{ padding: "12px 16px" }}>
                        <p style={{
                            fontSize: 10, fontWeight: 700, textTransform: "uppercase",
                            letterSpacing: "0.07em", color: "var(--muted-foreground)", marginBottom: 8,
                        }}>
                            Input
                        </p>
                        <TruncatedPayload data={d.input} />
                    </div>
                </>
            )}

            {/* Error section */}
            {d.error && (
                <>
                    <div style={{ height: 1, background: "var(--border)", margin: "0 16px" }} />
                    <div style={{ padding: "12px 16px" }}>
                        <p style={{
                            fontSize: 10, fontWeight: 700, textTransform: "uppercase",
                            letterSpacing: "0.07em", color: "#EF4444", marginBottom: 8,
                            display: "flex", alignItems: "center", gap: 5,
                        }}>
                            <AlertTriangle size={11} />
                            Error
                        </p>
                        <div style={{
                            padding: "10px 12px", borderRadius: 8,
                            background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.25)",
                            fontSize: 12, color: "#DC2626", lineHeight: 1.6, wordBreak: "break-word",
                        }}>
                            {d.error}
                        </div>
                    </div>
                </>
            )}

            {/* Output section */}
            {d.output && Object.keys(d.output).length > 0 && (
                <>
                    <div style={{ height: 1, background: "var(--border)", margin: "0 16px" }} />
                    <div style={{ padding: "12px 16px" }}>
                        <p style={{
                            fontSize: 10, fontWeight: 700, textTransform: "uppercase",
                            letterSpacing: "0.07em", color: "var(--muted-foreground)", marginBottom: 8,
                        }}>
                            Output
                        </p>
                        <TruncatedPayload data={d.output} />
                    </div>
                </>
            )}
        </div>
    );
}
