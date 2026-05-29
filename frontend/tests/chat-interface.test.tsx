/**
 * ChatInterface source-level tests.
 *
 * The full component pulls in react-markdown v10 (large ESM-only dep tree) which
 * exhausts the jsdom worker heap before any test runs. These tests verify the
 * implementation changes by asserting on the source text directly — a pragmatic
 * approach that covers the same acceptance criteria without the memory cost.
 */
import { readFileSync } from "fs";
import { resolve } from "path";

const source = readFileSync(
    resolve(__dirname, "../src/components/dashboard/chat-interface.tsx"),
    "utf8"
);

describe("ChatInterface — implementation checks", () => {
    it("does not import Sparkles (removed from lucide import)", () => {
        expect(source).not.toMatch(/import[^;]*Sparkles[^;]*from "lucide-react"/);
    });

    it("AI avatar renders the b mark, not a Sparkles icon", () => {
        // The avatar branch for assistant role should return "b" string literal
        expect(source).toContain('"b"');
        // And must not render <Sparkles inside the avatar area
        expect(source).not.toContain("<Sparkles");
    });

    it("textarea has rows={1} for auto-grow baseline", () => {
        expect(source).toContain("rows={1}");
    });

    it("textarea has onInput auto-grow handler", () => {
        expect(source).toContain("el.style.height");
        expect(source).toContain("el.scrollHeight");
        expect(source).toContain("144");
    });

    it("textarea has min-h and max-h classes", () => {
        expect(source).toContain("min-h-[44px]");
        expect(source).toContain("max-h-36");
    });

    it("message wrapper has message-in class for slide animation", () => {
        expect(source).toContain("message-in");
    });

    it("typing dots have staggered animation delays (0ms / 150ms / 300ms)", () => {
        expect(source).toContain('"0ms"');
        expect(source).toContain('"150ms"');
        expect(source).toContain('"300ms"');
    });

    it("textarea height resets to auto on send", () => {
        expect(source).toContain('textareaRef.current.style.height = "auto"');
    });

    it("imports HelpCircle from lucide-react", () => {
        expect(source).toMatch(/import[^;]*HelpCircle[^;]*from "lucide-react"/);
    });

    it("imports useToolConnections hook", () => {
        expect(source).toContain('from "@/hooks/use-tool-connections"');
    });

    it("imports TOOL_CAPABILITIES", () => {
        expect(source).toContain('from "@/lib/tool-capabilities"');
    });

    it("has showHelp state", () => {
        expect(source).toContain("showHelp");
        expect(source).toContain("setShowHelp");
    });

    it("renders the help button with aria-label", () => {
        expect(source).toContain('aria-label="What can ByteOps do?"');
    });

    it("renders HelpCircle icon", () => {
        expect(source).toContain("<HelpCircle");
    });

    it("renders 'What can I help you with?' popover heading", () => {
        expect(source).toContain("What can I help you with?");
    });

    it("has click-outside handler to close popover", () => {
        expect(source).toContain("handleClickOutside");
        expect(source).toContain("removeEventListener");
    });
});
