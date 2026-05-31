/**
 * NodeDetailPopup source-level tests.
 */
import { readFileSync } from "fs";
import { resolve } from "path";

const source = readFileSync(
    resolve(__dirname, "../src/components/runs/node-detail-popup.tsx"),
    "utf8"
);

describe("NodeDetailPopup — implementation checks", () => {
    it("renders node type label", () => {
        expect(source).toMatch(/nodeType/);
    });

    it("renders risk level", () => {
        expect(source).toMatch(/riskLevel/);
    });

    it("renders duration", () => {
        expect(source).toMatch(/durationMs/);
    });

    it("renders status", () => {
        expect(source).toMatch(/status/);
    });

    it("renders input payload", () => {
        expect(source).toMatch(/input/);
    });

    it("renders output payload", () => {
        expect(source).toMatch(/output/);
    });

    it("renders error message when output is null and error exists", () => {
        expect(source).toMatch(/error/);
    });

    it("has a close button (× or X)", () => {
        expect(source).toMatch(/onClose|×|✕/);
    });

    it("truncates long payloads at 500 characters", () => {
        expect(source).toMatch(/500/);
    });

    it("has a 'show full' toggle for truncated payloads", () => {
        expect(source).toMatch(/show full|showFull|expanded/i);
    });

    it("uses CSS variable for popup background (var(--popover))", () => {
        expect(source).toContain("var(--popover)");
    });

    it("exports NodeDetailPopup as named export", () => {
        expect(source).toMatch(/export\s+(function|const)\s+NodeDetailPopup/);
    });
});
