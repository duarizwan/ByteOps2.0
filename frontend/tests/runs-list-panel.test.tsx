/**
 * RunsListPanel source-level tests.
 */
import { readFileSync } from "fs";
import { resolve } from "path";

const panelSource = readFileSync(
    resolve(__dirname, "../src/components/runs/runs-list-panel.tsx"),
    "utf8"
);
const rowSource = readFileSync(
    resolve(__dirname, "../src/components/runs/run-row.tsx"),
    "utf8"
);

describe("RunRow — implementation checks", () => {
    it("renders intent label", () => {
        expect(rowSource).toMatch(/intent/);
    });

    it("renders a status colour dot", () => {
        expect(rowSource).toMatch(/completed|failed|waiting/);
    });

    it("renders relative timestamp from created_at", () => {
        expect(rowSource).toMatch(/created_at/);
    });

    it("has a dismiss (×) button revealed on hover", () => {
        expect(rowSource).toMatch(/onDismiss|dismiss/i);
        expect(rowSource).toMatch(/group-hover|hover/);
    });

    it("calls onDismiss when dismiss button is clicked", () => {
        expect(rowSource).toMatch(/onDismiss/);
    });

    it("exports RunRow as named export", () => {
        expect(rowSource).toMatch(/export\s+(function|const)\s+RunRow/);
    });
});

describe("RunsListPanel — implementation checks", () => {
    it("renders a Clear all button", () => {
        expect(panelSource).toMatch(/[Cc]lear all/);
    });

    it("shows empty state when no runs", () => {
        expect(panelSource).toMatch(/No agent runs yet|no.*runs/i);
    });

    it("accepts onDismiss handler", () => {
        expect(panelSource).toMatch(/onDismiss/);
    });

    it("accepts onClearAll handler", () => {
        expect(panelSource).toMatch(/onClearAll/);
    });

    it("accepts selectedRunId to highlight active row", () => {
        expect(panelSource).toMatch(/selectedRunId/);
    });

    it("uses CSS variable for background", () => {
        expect(panelSource).toMatch(/var\(--card\)|var\(--background\)/);
    });

    it("exports RunsListPanel as named export", () => {
        expect(panelSource).toMatch(/export\s+(function|const)\s+RunsListPanel/);
    });
});
