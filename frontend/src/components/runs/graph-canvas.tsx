"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
    ReactFlow,
    ReactFlowProvider,
    Background,
    Controls,
    useNodesState,
    useEdgesState,
    useReactFlow,
    MarkerType,
    Panel,
} from "@xyflow/react";
import { Maximize2, AlertCircle, Activity } from "lucide-react";
import { EllipseNode } from "./graph-nodes/ellipse-node";
import { NodeDetailPopup } from "./node-detail-popup";
import { graphTransformer, TYPE_COLOR, TYPE_BG_COLOR, BORDER_DASHED } from "@/lib/graph-transformer";
import { useAgentRun } from "@/hooks/use-agent-run";
import type { GraphNode, GraphNodeType } from "@/lib/graph-transformer";
import type { AgentRun } from "@/hooks/use-agent-runs";

const nodeTypes = { graphnode: EllipseNode };

const LEGEND: { type: GraphNodeType; label: string }[] = [
    { type: "user_input",     label: "User input" },
    { type: "intent_router",  label: "Router" },
    { type: "agent_plan",     label: "Plan" },
    { type: "tool_call",      label: "Tool call" },
    { type: "platform_api",   label: "Platform API" },
    { type: "approval_gate",  label: "Approval gate" },
    { type: "final_response", label: "Response" },
];

function formatDuration(createdAt: string, completedAt: string): string {
    const start = new Date(createdAt).getTime();
    const end = new Date(completedAt).getTime();
    const seconds = (end - start) / 1000;
    return `${seconds.toFixed(1)}s`;
}

function formatDateOnly(isoString: string): string {
    return new Date(isoString).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
    });
}

interface ExecutionHeaderProps {
    run: AgentRun;
}

function ExecutionHeader({ run }: ExecutionHeaderProps) {
    const shortId = run.id.slice(-8);
    const toolCallCount = run.steps.filter((s) => s.step_type === "tool_call").length;
    const duration = run.completed_at
        ? formatDuration(run.created_at, run.completed_at)
        : "running";

    return (
        <div style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: 24,
            padding: "8px 16px",
            fontSize: 11.5,
            color: "var(--muted-foreground)",
            backdropFilter: "blur(8px)",
            marginTop: 12,
            whiteSpace: "nowrap",
        }}>
            {/* Status badge */}
            <span style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                border: "1px solid #22C55E",
                background: "rgba(34, 197, 94, 0.1)",
                color: "#16A34A",
                borderRadius: 999,
                padding: "2px 8px",
                fontSize: 10.5,
                fontWeight: 500,
            }}>
                ● {run.status}
            </span>

            {/* Run ID */}
            <span>Run …{shortId}</span>

            <span style={{ color: "var(--border)" }}>|</span>

            {/* Intent */}
            <span>
                Intent:{" "}
                <strong style={{ color: "var(--foreground)" }}>{run.intent}</strong>
            </span>

            <span style={{ color: "var(--border)" }}>|</span>

            {/* Duration */}
            <span>{duration}</span>

            <span style={{ color: "var(--border)" }}>|</span>

            {/* Tool call count */}
            <span>{toolCallCount} tool calls</span>

            {/* Timestamp pushed to right */}
            <span style={{ marginLeft: "auto", color: "var(--muted-foreground)" }}>
                {formatDateOnly(run.created_at)}
            </span>
        </div>
    );
}

interface GraphCanvasProps {
    selectedRunId: string | null;
    onLoad?: () => void;
}

function GraphCanvasInner({ selectedRunId, onLoad }: GraphCanvasProps) {
    const { run, isLoading, error } = useAgentRun(selectedRunId);

    useEffect(() => {
        if (!isLoading && (run || error)) {
            onLoad?.();
        }
    }, [isLoading, run, error, onLoad]);
    const { fitView } = useReactFlow();
    const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

    const { nodes: derivedNodes, edges: derivedEdges } = useMemo(() => {
        if (!run) return { nodes: [], edges: [] };
        return graphTransformer(run);
    }, [run]);

    const [nodes, setNodes, onNodesChange] = useNodesState(derivedNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(derivedEdges);

    useEffect(() => {
        setNodes(derivedNodes);
        setEdges(
            derivedEdges.map((e) => ({
                ...e,
                markerEnd: { type: MarkerType.ArrowClosed, color: e.style.stroke },
            }))
        );
        setSelectedNode(null);
        const t = setTimeout(() => fitView({ padding: 0.25, duration: 400 }), 80);
        return () => clearTimeout(t);
    }, [derivedNodes, derivedEdges, setNodes, setEdges, fitView]);

    const handleNodeClick = useCallback((_: React.MouseEvent, node: { id: string; data: unknown; position: { x: number; y: number }; width?: number; height?: number }) => {
        setSelectedNode(node as GraphNode);
    }, []);

    const handlePaneClick = useCallback(() => setSelectedNode(null), []);
    const handleFitView = useCallback(() => fitView({ padding: 0.2, duration: 400 }), [fitView]);

    if (!selectedRunId) {
        return (
            <div className="flex flex-col items-center justify-center h-full gap-3" style={{ color: "var(--muted-foreground)" }}>
                <Activity size={32} style={{ opacity: 0.4 }} />
                <p className="text-sm">No run selected — pick one from the list.</p>
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-full text-sm gap-2" style={{ color: "var(--muted-foreground)" }}>
                <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                Loading run…
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-full gap-2">
                <AlertCircle size={28} className="text-destructive opacity-70" />
                <p className="text-sm text-destructive">{error}</p>
            </div>
        );
    }

    return (
        <div className="relative h-full w-full">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={handleNodeClick}
                onPaneClick={handlePaneClick}
                nodeTypes={nodeTypes}
                nodesDraggable
                fitView
                fitViewOptions={{ padding: 0.25 }}
                minZoom={0.25}
                maxZoom={2}
                style={{ background: "var(--background)" }}
                defaultEdgeOptions={{
                    type: "smoothstep",
                    style: { stroke: "var(--border)", strokeWidth: 1.5 },
                    markerEnd: { type: MarkerType.ArrowClosed, color: "var(--border)" },
                }}
            >
                <Background color="var(--border)" gap={28} size={1} />
                <Controls
                    style={{
                        background: "var(--card)",
                        border: "1px solid var(--border)",
                        borderRadius: 10,
                    }}
                    showInteractive={false}
                />

                {/* Execution header */}
                {run && (
                    <Panel position="top-center">
                        <ExecutionHeader run={run as AgentRun} />
                    </Panel>
                )}

                {/* Fit view button */}
                <Panel position="top-right">
                    <button
                        onClick={handleFitView}
                        title="Fit view"
                        style={{
                            background: "var(--card)",
                            border: "1px solid var(--border)",
                            borderRadius: 8,
                            padding: "6px 10px",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                            fontSize: 12,
                            color: "var(--foreground)",
                        }}
                    >
                        <Maximize2 size={13} />
                        Fit view
                    </button>
                </Panel>

                {/* Legend */}
                <Panel position="bottom-center">
                    <div style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: 12,
                        justifyContent: "center",
                        padding: "8px 14px",
                        background: "var(--card)",
                        border: "1px solid var(--border)",
                        borderRadius: 12,
                        backdropFilter: "blur(8px)",
                        marginBottom: 10,
                    }}>
                        {LEGEND.map(({ type, label }) => (
                            <div key={type} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                                <div style={{
                                    width: 10,
                                    height: 10,
                                    borderRadius: 3,
                                    border: `1.5px ${BORDER_DASHED[type] ? "dashed" : "solid"} ${TYPE_COLOR[type]}`,
                                    background: TYPE_BG_COLOR[type],
                                    flexShrink: 0,
                                }} />
                                <span style={{ fontSize: 10.5, color: "var(--muted-foreground)" }}>{label}</span>
                            </div>
                        ))}
                    </div>
                </Panel>
            </ReactFlow>

            {selectedNode && (
                <NodeDetailPopup
                    node={selectedNode}
                    onClose={() => setSelectedNode(null)}
                />
            )}
        </div>
    );
}

export function GraphCanvas({ selectedRunId, onLoad }: GraphCanvasProps) {
    return (
        <ReactFlowProvider>
            <GraphCanvasInner selectedRunId={selectedRunId} onLoad={onLoad} />
        </ReactFlowProvider>
    );
}
