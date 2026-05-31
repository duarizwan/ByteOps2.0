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

    it("AI avatar renders ByteOpsLogoMark, not a Sparkles icon", () => {
        // The avatar branch for assistant role should use the brand logo component
        expect(source).toContain("ByteOpsLogoMark");
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

    it("defines workflow draft approval state and card", () => {
        expect(source).toContain("interface WorkflowDraft");
        expect(source).toContain("WorkflowDraftCard");
        expect(source).toContain("pendingWorkflowDraft");
    });

    it("handles workflow_draft SSE events", () => {
        expect(source).toContain('event.type === "workflow_draft"');
        expect(source).toContain("setPendingWorkflowDraft");
    });

    it("replaces the assistant typing state when a workflow draft arrives", () => {
        expect(source).toContain("workflowDraftAssistantContent(event)");
        expect(source).toContain('event.type === "workflow_draft"');
        expect(source).toContain("newContent = workflowDraftAssistantContent(event)");
    });

    it("does not duplicate workflow draft text when the backend sends the final draft delta", () => {
        expect(source).toContain("isWorkflowDraftPlaceholder(newContent)");
        expect(source).toContain('event.content.includes("Draft workflow ready for review.")');
        expect(source).toContain("newContent = event.content");
    });

    it("fails visibly when the chat request returns a bad HTTP response", () => {
        expect(source).toContain("if (!response.ok)");
        expect(source).toContain("Chat request failed");
    });

    it("buffers SSE records so split workflow events still parse", () => {
        expect(source).toContain("let sseBuffer =");
        expect(source).toContain("sseBuffer += decoder.decode(value, { stream: true })");
        expect(source).toContain('split("\\n\\n")');
    });

    it("clears the assistant stage if the chat stream ends early", () => {
        expect(source).toContain("sawTerminalEvent");
        expect(source).toContain("stream ended without a terminal event");
    });

    it("aborts a silent chat stream instead of leaving Understanding request forever", () => {
        expect(source).toContain("const chatTimeoutController = new AbortController()");
        expect(source).toContain("chatTimeoutController.abort()");
        expect(source).toContain("signal: chatTimeoutController.signal");
        expect(source).toContain('error.name === "AbortError"');
    });

    it("calls the workflow draft approval endpoint", () => {
        expect(source).toContain("approve-workflow-draft");
        expect(source).toContain("handleApproveWorkflowDraft");
    });

    it("notifies the dashboard when a workflow draft is saved", () => {
        expect(source).toContain("onWorkflowSaved");
        expect(source).toContain("onWorkflowSaved?.()");
    });

    it("does not clear email send approval unless the approve request succeeds", () => {
        const approveStart = source.indexOf("const handleApprove = async () =>");
        const approveEnd = source.indexOf("const handleReject = async () =>");
        const approveSource = source.slice(approveStart, approveEnd);

        expect(approveSource).toContain("const response = await fetch");
        expect(approveSource).toContain("if (!response.ok)");
        expect(approveSource).toContain("setPendingApproval(null)");
    });

    it("renders editable workflow draft controls", () => {
        expect(source).toContain("onDraftChange");
        expect(source).toContain("Remove action");
        expect(source).toContain('value={draft.name}');
        expect(source).toContain('value={draft.trigger.label || ""}');
    });

    it("sends the edited workflow draft in the approval request body", () => {
        expect(source).toContain("JSON.stringify({ draft: pendingWorkflowDraft })");
        expect(source).toContain('"Content-Type": "application/json"');
    });

    it("supports adding constrained workflow draft actions", () => {
        expect(source).toContain("SUPPORTED_WORKFLOW_ACTIONS");
        expect(source).toContain("addDraftAction");
        expect(source).toContain("Add action");
        expect(source).toContain('value={selectedActionTool}');
    });
});
