"use client";

import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import {
    MessageCircle,
    GitBranch,
    FileText,
    Wrench,
    Server,
    ShieldCheck,
    CheckCircle2,
    Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { GraphNodeData, GraphNodeType } from "@/lib/graph-transformer";
import { TYPE_LABEL_COLOR } from "@/lib/graph-transformer";

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

export const EllipseNode = memo(function EllipseNode({ data, selected }: NodeProps) {
    const d = data as unknown as GraphNodeData;
    const isFailed = d.status === "failed";

    const labelColor = isFailed ? "#f87171" : TYPE_LABEL_COLOR[d.nodeType];
    const borderColor = isFailed ? "#EF4444" : d.typeColor;
    const bgColor = isFailed ? "#1A0808" : `color-mix(in srgb, ${d.typeColor} 12%, var(--card))`;

    const Icon = ICONS[d.nodeType] ?? Wrench;

    const boxShadow = selected
        ? `0 0 0 2px ${borderColor}80, 0 0 28px ${borderColor}40`
        : `0 0 0 1px ${borderColor}26, 0 0 20px ${borderColor}18`;

    return (
        <>
            <Handle type="target" position={Position.Top} style={{ opacity: 0, pointerEvents: "none" }} />
            <div style={{
                position: "relative",
                minWidth: 168,
                maxWidth: 220,
                borderRadius: 14,
                padding: "12px 16px",
                background: bgColor,
                border: d.borderDashed ? "none" : `1.5px solid ${borderColor}`,
                boxShadow,
                cursor: "grab",
                userSelect: "none",
                textAlign: "center",
                transition: "box-shadow 0.2s ease",
            }}>
                {d.borderDashed && (
                    <svg
                        style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none", overflow: "visible", borderRadius: 14 }}
                    >
                        <rect
                            x="0.75" y="0.75"
                            width="99%" height="96%"
                            rx="13.5" ry="13.5"
                            fill="none"
                            stroke={borderColor}
                            strokeWidth="1.5"
                            strokeDasharray="9 5"
                        />
                    </svg>
                )}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 7, marginBottom: 4 }}>
                    <Icon size={14} color={labelColor} strokeWidth={1.5} />
                    <span
                        className="font-mono"
                        style={{
                            fontSize: 13.5,
                            fontWeight: 600,
                            color: labelColor,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            maxWidth: 168,
                        }}
                        title={d.label}
                    >
                        {d.label}
                    </span>
                </div>
                {d.sublabel && (
                    <div style={{
                        fontSize: 11,
                        color: "var(--muted-foreground)",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                    }}>
                        {d.sublabel}
                    </div>
                )}
            </div>
            <Handle type="source" position={Position.Bottom} style={{ opacity: 0, pointerEvents: "none" }} />
        </>
    );
});
