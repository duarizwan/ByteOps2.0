import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ReactFlowProvider } from "@xyflow/react";
import { EllipseNode } from "@/components/runs/graph-nodes/ellipse-node";
import type { GraphNodeData } from "@/lib/graph-transformer";

function makeData(anomalyScore: number | null): GraphNodeData {
    return {
        label: "Forward Email", sublabel: "ok", nodeType: "platform_api",
        riskLevel: "EXTERNAL_SEND", durationMs: null, status: "completed",
        input: null, output: null, error: null,
        typeColor: "#10B981", bgColor: "#071A12", borderDashed: true,
        anomalyScore,
    };
}

function renderNode(data: GraphNodeData) {
    return render(
        <ReactFlowProvider>
            <EllipseNode id="n1" data={data as unknown as Record<string, unknown>} selected={false}
                type="graphnode" dragging={false} zIndex={0} isConnectable={false}
                positionAbsoluteX={0} positionAbsoluteY={0} />
        </ReactFlowProvider>
    );
}

describe("EllipseNode anomaly heat", () => {
    it("shows an anomaly marker when score is high", () => {
        const { container } = renderNode(makeData(0.95));
        expect(container.querySelector('[data-anomaly="high"]')).not.toBeNull();
    });

    it("renders no anomaly marker when score is null", () => {
        const { container } = renderNode(makeData(null));
        expect(container.querySelector('[data-anomaly]')).toBeNull();
    });
});
