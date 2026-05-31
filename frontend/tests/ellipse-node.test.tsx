/**
 * EllipseNode source-level tests — graph-v2 style (rounded rect, colored bg+border).
 */
import { readFileSync } from "fs";
import { resolve } from "path";

const source = readFileSync(
    resolve(__dirname, "../src/components/runs/graph-nodes/ellipse-node.tsx"),
    "utf8"
);

describe("EllipseNode — implementation checks", () => {
    it("uses border-radius for rounded rectangle shape", () => {
        expect(source).toMatch(/borderRadius/);
    });

    it("renders node label in a monospace font class", () => {
        expect(source).toMatch(/font-mono/);
    });

    it("applies typeColor as border and label color", () => {
        expect(source).toMatch(/typeColor|borderColor/);
    });

    it("uses color-mix for tinted background from type color", () => {
        expect(source).toMatch(/color-mix/);
    });

    it("renders sublabel for contextual info", () => {
        expect(source).toMatch(/sublabel/);
    });

    it("renders status", () => {
        expect(source).toMatch(/status/);
    });

    it("uses CSS variable for card background", () => {
        expect(source).toContain("var(--card)");
    });

    it("uses borderDashed for dashed node types (platform api, approval)", () => {
        expect(source).toMatch(/borderDashed/);
    });

    it("applies red color for failed status nodes", () => {
        expect(source).toMatch(/failed/);
        expect(source).toMatch(/#f87171/);
    });

    it("exports EllipseNode as named export", () => {
        expect(source).toMatch(/export\s+(function|const)\s+EllipseNode/);
    });
});
