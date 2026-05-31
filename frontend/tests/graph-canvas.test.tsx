/**
 * GraphCanvas source-level tests.
 * Avoids @xyflow/react heavy ESM transform — asserts on component source instead.
 */
import { readFileSync } from "fs";
import { resolve } from "path";

const source = readFileSync(
    resolve(__dirname, "../src/components/runs/graph-canvas.tsx"),
    "utf8"
);

describe("GraphCanvas — implementation checks", () => {
    it("imports ReactFlow from @xyflow/react", () => {
        expect(source).toMatch(/@xyflow\/react/);
    });

    it("registers EllipseNode as a custom node type", () => {
        expect(source).toMatch(/graphnode.*EllipseNode|EllipseNode.*graphnode/);
    });

    it("uses smoothstep or similar edge type with arrowhead", () => {
        expect(source).toMatch(/smoothstep|arrowclosed/);
    });

    it("calls graphTransformer to derive nodes and edges from run", () => {
        expect(source).toContain("graphTransformer");
    });

    it("renders fit-view button", () => {
        expect(source).toMatch(/[Ff]it[Vv]iew|fit-view|fitView/);
    });

    it("uses CSS variable for canvas background", () => {
        expect(source).toMatch(/var\(--background\)/);
    });

    it("uses a stroke color for edges", () => {
        expect(source).toMatch(/stroke.*#334155|#334155.*stroke|muted-foreground/);
    });

    it("shows empty state when no run is selected", () => {
        expect(source).toMatch(/No run selected|no.*run|empty/i);
    });

    it("shows error state for failed fetches", () => {
        expect(source).toMatch(/not found|unavailable|error/i);
    });

    it("exports GraphCanvas as named export", () => {
        expect(source).toMatch(/export\s+(function|const)\s+GraphCanvas/);
    });
});
