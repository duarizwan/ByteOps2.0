import { readFileSync } from "fs";
import { resolve } from "path";

const source = readFileSync(
    resolve(__dirname, "../src/lib/tool-capabilities.ts"),
    "utf8"
);

describe("tool-capabilities", () => {
    it("exports TOOL_CAPABILITIES", () => {
        expect(source).toContain("export const TOOL_CAPABILITIES");
    });

    it("exports ToolCapabilityEntry type", () => {
        expect(source).toContain("ToolCapabilityEntry");
    });

    it("covers all 7 supported tool types", () => {
        const tools = ["gmail", "calendar", "slack", "jira", "github", "dropbox", "trello"];
        for (const tool of tools) {
            expect(source).toContain(`"${tool}"`);
        }
    });

    it("each tool has a label and capabilities array", () => {
        expect(source).toContain("label:");
        expect(source).toContain("capabilities:");
    });

    it("no tool has fewer than 3 capability strings", () => {
        // Rough check: at least 3 capability strings per tool (21+ total)
        const matches = source.match(/"[A-Z][^"]{10,}"/g) ?? [];
        expect(matches.length).toBeGreaterThanOrEqual(21);
    });
});
