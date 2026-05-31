import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import React from "react";

const notificationState = vi.hoisted(() => ({
    notifications: [] as Array<{
        id: string;
        source_tool: string;
        title: string;
        content: string | null;
        priority: "low" | "medium" | "high" | "urgent";
        is_read: boolean;
        created_at: string;
        metadata?: Record<string, unknown>;
    }>,
}));
const workflowState = vi.hoisted(() => ({
    workflows: [] as Array<{
        id: string;
        name: string;
        description: string | null;
        status: "active" | "paused" | "running" | "failed" | "waiting_approval";
        trigger_label: string;
        action_summary: string;
        condition_summary?: string;
        action_count?: number;
        approval_required?: boolean;
        approval_summary?: string;
        actions?: unknown[];
        last_run_at: string | null;
        next_run_at: string | null;
        last_error: string | null;
        last_agent_run_id?: string | null;
        last_run_status?: string | null;
        last_run_summary?: string | null;
        needs_attention?: boolean;
        consecutive_failure_count?: number;
        last_failure_at?: string | null;
    }>,
    isLoading: false,
}));
const workflowActions = vi.hoisted(() => ({
    pause: vi.fn(),
    resume: vi.fn(),
    runNow: vi.fn(),
    refresh: vi.fn(),
}));
const agentRunState = vi.hoisted(() => ({
    runs: [] as Array<{
        id: string;
        intent: string;
        status: "planning" | "waiting_approval" | "running" | "completed" | "failed" | "cancelled";
        plan: Record<string, unknown> | null;
        final_response: string | null;
        error: string | null;
        metadata?: Record<string, unknown> | null;
        steps: unknown[];
        created_at: string;
        updated_at?: string;
        completed_at?: string | null;
    }>,
    isLoading: false,
}));

vi.mock("@clerk/nextjs", () => ({
    useAuth: () => ({ getToken: vi.fn().mockResolvedValue("tok") }),
}));
vi.mock("@/hooks/use-notifications", () => ({
    useNotifications: () => ({
        notifications: notificationState.notifications,
        unreadCount: notificationState.notifications.filter((n) => !n.is_read).length,
        isLoading: false,
        markRead: vi.fn(),
        markAllRead: vi.fn(),
        dismiss: vi.fn(),
        refresh: vi.fn(),
    }),
}));
vi.mock("@/hooks/use-workflows", () => ({
    useWorkflows: () => ({
        workflows: workflowState.workflows,
        isLoading: workflowState.isLoading,
        pause: workflowActions.pause,
        resume: workflowActions.resume,
        runNow: workflowActions.runNow,
        refresh: workflowActions.refresh,
    }),
}));
vi.mock("@/hooks/use-agent-runs", () => ({
    useAgentRuns: () => ({
        runs: agentRunState.runs,
        isLoading: agentRunState.isLoading,
        refresh: vi.fn(),
    }),
}));
vi.mock("@/lib/brand-icons", () => ({ getBrandIconUrl: () => null }));

import { ContextPanel } from "@/components/dashboard/context-panel";

const props = {
    isCollapsed: false,
    onToggleCollapse: vi.fn(),
};

describe("ContextPanel", () => {
    beforeEach(() => {
        notificationState.notifications = [];
        workflowState.workflows = [];
        workflowState.isLoading = false;
        workflowActions.pause.mockReset();
        workflowActions.resume.mockReset();
        workflowActions.runNow.mockReset();
        workflowActions.refresh.mockReset();
        agentRunState.runs = [];
        agentRunState.isLoading = false;
    });

    it("tab label spans use hidden lg:inline, not hidden xl:inline", () => {
        const { container } = render(<ContextPanel {...props} />);
        const xlSpans = container.querySelectorAll(".hidden.xl\\:inline");
        expect(xlSpans).toHaveLength(0);
        const lgSpans = container.querySelectorAll(".hidden.lg\\:inline");
        expect(lgSpans.length).toBeGreaterThan(0);
    });

    it("exposes a refresh callback that also refreshes workflows", () => {
        const refreshRef = { current: null as null | (() => void) };
        render(<ContextPanel {...props} onRefreshRef={refreshRef} />);

        refreshRef.current?.();

        expect(workflowActions.refresh).toHaveBeenCalledTimes(1);
    });

    it("routes Gmail and Slack action items to Tasks instead of Alerts", () => {
        notificationState.notifications = [
            {
                id: "gmail-task",
                source_tool: "gmail",
                title: "Budget approval needed",
                content: "Maya asked you to approve the revised budget by Friday.",
                priority: "high",
                is_read: false,
                created_at: "2026-05-29T10:00:00.000Z",
                metadata: { category: "task", action_required: true },
            },
            {
                id: "slack-task",
                source_tool: "slack",
                title: "Review launch checklist",
                content: "A Slack message asks you to review the launch checklist today.",
                priority: "medium",
                is_read: false,
                created_at: "2026-05-29T10:01:00.000Z",
                metadata: { category: "task" },
            },
            {
                id: "gmail-alert",
                source_tool: "gmail",
                title: "CFO sent contract update",
                content: "Important email extracted from Gmail.",
                priority: "high",
                is_read: false,
                created_at: "2026-05-29T10:02:00.000Z",
                metadata: { category: "alert" },
            },
        ];

        render(<ContextPanel {...props} />);

        expect(screen.queryByText("Budget approval needed")).not.toBeInTheDocument();
        expect(screen.queryByText("Review launch checklist")).not.toBeInTheDocument();
        expect(screen.getByText("CFO sent contract update")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: /tasks/i }));

        expect(screen.getByText("Budget approval needed")).toBeInTheDocument();
        expect(screen.getByText("Review launch checklist")).toBeInTheDocument();
        expect(screen.queryByText("CFO sent contract update")).not.toBeInTheDocument();
    });

    it("shows available older tasks when there are no tasks for the default today filter", () => {
        notificationState.notifications = [
            {
                id: "yesterday-task",
                source_tool: "jira",
                title: "Review QA findings",
                content: "Please review the ByteOps QA findings.",
                priority: "medium",
                is_read: false,
                created_at: "2000-01-01T10:00:00.000Z",
                metadata: { category: "task", action_required: true },
            },
        ];

        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /tasks/i }));

        expect(screen.getByText("Review QA findings")).toBeInTheDocument();
    });

    it("shows extracted attention text instead of the raw chat query in Alerts", () => {
        notificationState.notifications = [
            {
                id: "chat-alert",
                source_tool: "gmail",
                title: "check my gmail for anything important",
                content: "The CFO shared a contract update that needs attention.",
                priority: "medium",
                is_read: false,
                created_at: "2026-05-29T10:00:00.000Z",
                metadata: {
                    from_chat: true,
                    category: "alert",
                    attention_title: "CFO contract update needs attention",
                    extracted_priority: "high",
                },
            },
        ];

        render(<ContextPanel {...props} />);

        expect(screen.getByText("CFO contract update needs attention")).toBeInTheDocument();
        expect(screen.queryByText("check my gmail for anything important")).not.toBeInTheDocument();
        expect(screen.getByText("high")).toBeInTheDocument();
    });

    it("removes markdown and table marker characters from activity cards", () => {
        notificationState.notifications = [
            {
                id: "clean-alert",
                source_tool: "gmail",
                title: "*CFO* | contract - update",
                content: "- Please review | contract *terms* today.",
                priority: "high",
                is_read: false,
                created_at: "2026-05-29T10:00:00.000Z",
                metadata: { category: "alert" },
            },
        ];

        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /tasks/i }));

        expect(screen.getByText("CFO contract update")).toBeInTheDocument();
        expect(screen.getByText("Please review contract terms today.")).toBeInTheDocument();
        expect(screen.queryByText("*CFO* | contract - update")).not.toBeInTheDocument();
        expect(screen.queryByText("- Please review | contract *terms* today.")).not.toBeInTheDocument();
    });

    // ── Classifier: discard path ──────────────────────────────────────────────

    it("silently discards info/fyi notifications — absent from both Alerts and Tasks", () => {
        notificationState.notifications = [
            {
                id: "info-1",
                source_tool: "gmail",
                title: "Your email was sent",
                content: "Message delivered successfully.",
                priority: "low",
                is_read: false,
                created_at: "2026-05-29T10:00:00.000Z",
                metadata: { category: "info" },
            },
        ];

        render(<ContextPanel {...props} />);
        // Alerts tab is active by default
        expect(screen.queryByText("Your email was sent")).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: /tasks/i }));
        expect(screen.queryByText("Your email was sent")).not.toBeInTheDocument();
    });

    it("silently discards low-priority notification with no metadata and no matching text", () => {
        notificationState.notifications = [
            {
                id: "fyi-1",
                source_tool: "github",
                title: "PR #42 was merged by Alice",
                content: null,
                priority: "low",
                is_read: false,
                created_at: "2026-05-29T10:00:00.000Z",
                metadata: {},
            },
        ];

        render(<ContextPanel {...props} />);
        expect(screen.queryByText("PR #42 was merged by Alice")).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: /tasks/i }));
        expect(screen.queryByText("PR #42 was merged by Alice")).not.toBeInTheDocument();
    });

    // ── Classifier: alert path ─────────────────────────────────────────────────

    it("routes auth_error notification to Alerts and elevates priority to high", () => {
        notificationState.notifications = [
            {
                id: "auth-1",
                source_tool: "gmail",
                title: "Gmail token expired",
                content: "Re-authorize to continue using Gmail.",
                priority: "medium",
                is_read: false,
                created_at: "2026-05-29T10:00:00.000Z",
                metadata: { auth_error: true },
            },
        ];

        render(<ContextPanel {...props} />);
        expect(screen.getByText("Gmail token expired")).toBeInTheDocument();
        expect(screen.getByText("high")).toBeInTheDocument();
    });

    it("routes category:alert notification to Alerts and preserves medium priority", () => {
        notificationState.notifications = [
            {
                id: "alert-1",
                source_tool: "github",
                title: "Build failed on your PR",
                content: "CI failed on PR #99.",
                priority: "medium",
                is_read: false,
                created_at: "2026-05-29T10:00:00.000Z",
                metadata: { category: "alert" },
            },
        ];

        render(<ContextPanel {...props} />);
        expect(screen.getByText("Build failed on your PR")).toBeInTheDocument();
        expect(screen.getByText("medium")).toBeInTheDocument();
    });

    it("routes build_failure notification to Alerts and elevates priority to high", () => {
        notificationState.notifications = [
            {
                id: "build-1",
                source_tool: "github",
                title: "Deployment failed",
                content: "Production deploy failed at step 3.",
                priority: "medium",
                is_read: false,
                created_at: "2026-05-29T10:00:00.000Z",
                metadata: { build_failure: true },
            },
        ];

        render(<ContextPanel {...props} />);
        expect(screen.getByText("Deployment failed")).toBeInTheDocument();
        expect(screen.getByText("high")).toBeInTheDocument();
    });

    it("routes text-signal alert (contains 'failed') to Alerts when no metadata category", () => {
        notificationState.notifications = [
            {
                id: "text-alert-1",
                source_tool: "slack",
                title: "Slack sync failed",
                content: "Connection to workspace lost.",
                priority: "medium",
                is_read: false,
                created_at: "2026-05-29T10:00:00.000Z",
                metadata: {},
            },
        ];

        render(<ContextPanel {...props} />);
        expect(screen.getByText("Slack sync failed")).toBeInTheDocument();
    });

    // ── Priority: backend extracted_priority overrides frontend inference ──────

    it("respects backend extracted_priority:medium even when text signals suggest high", () => {
        notificationState.notifications = [
            {
                id: "prio-1",
                source_tool: "jira",
                title: "Ticket deadline approaching",
                content: "JIRA ticket overdue by 1 day.",
                priority: "low",
                is_read: false,
                created_at: "2026-05-29T10:00:00.000Z",
                metadata: { category: "alert", extracted_priority: "medium" },
            },
        ];

        render(<ContextPanel {...props} />);
        expect(screen.getByText("Ticket deadline approaching")).toBeInTheDocument();
        expect(screen.getByText("medium")).toBeInTheDocument();
        expect(screen.queryByText("high")).not.toBeInTheDocument();
    });

    it("renders workflow cards with status, trigger, actions, and clean errors", () => {
        workflowState.workflows = [
            {
                id: "workflow-1",
                name: "Daily inbox triage",
                description: "Summarize important emails each morning.",
                status: "active",
                trigger_label: "Every weekday at 9:00 AM",
                condition_summary: "Run when schedule is due.",
                action_summary: "Summarize unread important emails",
                action_count: 2,
                approval_required: true,
                approval_summary: "Approval required before external changes.",
                actions: [
                    { tool: "gmail", label: "Summarize unread important emails" },
                    { tool: "slack", label: "Post Slack update" },
                ],
                last_run_at: "2026-05-29T09:00:00.000Z",
                next_run_at: "2026-05-30T09:00:00.000Z",
                last_error: null,
                last_agent_run_id: "run-123",
                last_run_status: "completed",
                last_run_summary: "Workflow completed 2 actions.",
                needs_attention: false,
            },
            {
                id: "workflow-2",
                name: "Slack follow-up monitor",
                description: null,
                status: "failed",
                trigger_label: "Manual run",
                condition_summary: "Run only when started manually.",
                action_summary: "Find unanswered mentions",
                action_count: 1,
                actions: [{ tool: "slack", label: "Find unanswered mentions" }],
                last_run_at: null,
                next_run_at: null,
                last_error: "Slack | token - expired",
                needs_attention: true,
            },
        ];
        agentRunState.runs = [
            {
                id: "run-123",
                intent: "workflow",
                status: "completed",
                plan: { summary: "Run workflow: Daily inbox triage" },
                final_response: "Workflow completed 2 actions.",
                error: null,
                metadata: { workflow_id: "workflow-1" },
                steps: [],
                created_at: "2026-05-30T09:00:00.000Z",
                updated_at: "2026-05-30T09:01:00.000Z",
                completed_at: "2026-05-30T09:01:00.000Z",
            },
        ];

        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /workflows/i }));

        expect(screen.getByText("Daily inbox triage")).toBeInTheDocument();
        expect(screen.getByText("Active")).toBeInTheDocument();
        expect(screen.getByText("Every weekday at 9:00 AM")).toBeInTheDocument();
        expect(screen.getByText("Run when schedule is due.")).toBeInTheDocument();
        expect(screen.getByText("Summarize unread important emails")).toBeInTheDocument();
        expect(screen.getByText("2 actions")).toBeInTheDocument();
        expect(screen.getAllByText("Workflow completed 2 actions.").length).toBeGreaterThan(0);
        expect(screen.getByText(/view run/i)).toBeInTheDocument();
        expect(screen.getByText("Slack follow up monitor")).toBeInTheDocument();
        expect(screen.getByText("Failed")).toBeInTheDocument();
        expect(screen.getByText("Slack token expired")).toBeInTheDocument();
        expect(screen.queryByText("Workflows coming soon")).not.toBeInTheDocument();

        fireEvent.click(screen.getAllByRole("button", { name: /details/i })[0]);
        expect(screen.getByText("Actions")).toBeInTheDocument();
        expect(screen.getByText("Condition")).toBeInTheDocument();
        expect(screen.getByText("Action preview")).toBeInTheDocument();
        expect(screen.getByText("Gmail")).toBeInTheDocument();
        expect(screen.getByText("Post Slack update")).toBeInTheDocument();
        expect(screen.getByText("Approval gate")).toBeInTheDocument();
        expect(screen.getByText("Approval required before external changes.")).toBeInTheDocument();
        expect(screen.getByText("Last result")).toBeInTheDocument();
        expect(screen.getByText("Recent runs")).toBeInTheDocument();
        expect(screen.getAllByText("Workflow completed 2 actions.").length).toBeGreaterThan(1);
        fireEvent.click(screen.getByRole("button", { name: /close/i }));
        expect(screen.queryByText("Last result")).not.toBeInTheDocument();
    });

    it("shows workflow retry status and last failure details", () => {
        workflowState.workflows = [
            {
                id: "workflow-retry",
                name: "Daily inbox triage",
                description: null,
                status: "active",
                trigger_label: "Daily",
                action_summary: "Summarize Gmail",
                action_count: 1,
                actions: [{ tool: "gmail", label: "Summarize Gmail" }],
                last_run_at: "2026-05-31T09:00:00.000Z",
                next_run_at: "2026-05-31T09:15:00.000Z",
                last_error: "Workflow completed 0 of 1 action(s).",
                last_agent_run_id: "run-failed",
                last_run_status: "failed",
                last_run_summary: "Workflow completed 0 of 1 action(s).",
                needs_attention: true,
                consecutive_failure_count: 2,
                last_failure_at: "2026-05-31T09:00:00.000Z",
            },
        ];

        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /workflows/i }));

        expect(screen.getByText("Retry 2 of 3")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: /details/i }));
        expect(screen.getByText("Retry status")).toBeInTheDocument();
        expect(screen.getAllByText("Retry 2 of 3").length).toBeGreaterThan(1);
        expect(screen.getByText(/Last failure/)).toBeInTheDocument();
    });

    it("shows latest workflow run steps and output summaries in details", () => {
        workflowState.workflows = [
            {
                id: "workflow-steps",
                name: "Daily inbox triage",
                description: null,
                status: "active",
                trigger_label: "Manual run",
                action_summary: "Summarize Gmail",
                action_count: 1,
                actions: [{ tool: "gmail", label: "Summarize Gmail" }],
                last_run_at: "2026-05-31T09:00:00.000Z",
                next_run_at: null,
                last_error: null,
                last_agent_run_id: "run-with-steps",
                last_run_status: "completed",
                last_run_summary: "Workflow completed 1 of 1 action(s).",
                needs_attention: false,
            },
        ];
        agentRunState.runs = [
            {
                id: "run-with-steps",
                intent: "workflow",
                status: "completed",
                plan: { summary: "Run workflow: Daily inbox triage" },
                final_response: "Workflow completed 1 of 1 action(s).",
                error: null,
                metadata: { workflow_id: "workflow-steps" },
                steps: [
                    {
                        id: "step-gmail",
                        step_type: "tool_call",
                        name: "workflow_action:gmail",
                        status: "completed",
                        input: null,
                        output: {
                            status: "completed",
                            summary: "Summarized Gmail inbox.",
                        },
                        error: null,
                        created_at: "2026-05-31T09:00:01.000Z",
                    },
                    {
                        id: "step-final",
                        step_type: "final",
                        name: "workflow_actions",
                        status: "completed",
                        input: null,
                        output: {
                            completed_count: 1,
                            failed_count: 0,
                        },
                        error: null,
                        created_at: "2026-05-31T09:00:02.000Z",
                    },
                ],
                created_at: "2026-05-31T09:00:00.000Z",
                updated_at: "2026-05-31T09:00:02.000Z",
                completed_at: "2026-05-31T09:00:02.000Z",
            },
        ];

        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /workflows/i }));
        fireEvent.click(screen.getByRole("button", { name: /view run/i }));

        expect(screen.getByText("Run steps")).toBeInTheDocument();
        expect(screen.getByText("workflow action gmail")).toBeInTheDocument();
        expect(screen.getByText("Summarized Gmail inbox.")).toBeInTheDocument();
        expect(screen.getByText("workflow actions")).toBeInTheDocument();
        expect(screen.getByText("Completed 1. Failed 0.")).toBeInTheDocument();
    });

    it("shows latest workflow run metadata, output, error, and trace id in details", () => {
        workflowState.workflows = [
            {
                id: "workflow-run-details",
                name: "Daily inbox triage",
                description: null,
                status: "failed",
                trigger_label: "Manual run",
                action_summary: "Summarize Gmail",
                action_count: 1,
                actions: [{ tool: "gmail", label: "Summarize Gmail" }],
                last_run_at: "2026-05-31T09:00:00.000Z",
                next_run_at: null,
                last_error: "Gmail | token - expired",
                last_agent_run_id: "run-details",
                last_run_status: "failed",
                last_run_summary: "Workflow completed 0 of 1 action(s).",
                needs_attention: true,
            },
        ];
        agentRunState.runs = [
            {
                id: "run-details",
                intent: "workflow",
                status: "failed",
                plan: { summary: "Run workflow: Daily inbox triage" },
                final_response: "Workflow completed 0 of 1 action(s).",
                error: "Gmail token expired",
                metadata: { workflow_id: "workflow-run-details" },
                steps: [],
                created_at: "2026-05-31T09:00:00.000Z",
                updated_at: "2026-05-31T09:00:02.000Z",
                completed_at: "2026-05-31T09:00:02.000Z",
            },
        ];

        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /workflows/i }));
        fireEvent.click(screen.getByRole("button", { name: /details/i }));

        expect(screen.getByText("Latest run")).toBeInTheDocument();
        expect(screen.getByText("Run status")).toBeInTheDocument();
        expect(screen.getAllByText("Failed").length).toBeGreaterThan(1);
        expect(screen.getByText("Started")).toBeInTheDocument();
        expect(screen.getByText("Completed")).toBeInTheDocument();
        expect(screen.getByText("Output")).toBeInTheDocument();
        expect(screen.getAllByText("Workflow completed 0 of 1 action(s).").length).toBeGreaterThan(1);
        expect(screen.getByText("Error")).toBeInTheDocument();
        expect(screen.getAllByText("Gmail token expired").length).toBeGreaterThan(1);
        expect(screen.getByText("Trace ID")).toBeInTheDocument();
        expect(screen.getByText("run details")).toBeInTheDocument();
        const traceLink = screen.getByRole("link", { name: /view trace/i });
        expect(traceLink).toHaveAttribute("href", "/runs?trace=run-details");
    });

    it("marks a workflow run button as running while manual execution is pending", () => {
        workflowActions.runNow.mockImplementation(() => new Promise(() => undefined));
        workflowState.workflows = [
            {
                id: "workflow-run",
                name: "Daily inbox triage",
                description: null,
                status: "active",
                trigger_label: "Manual run",
                action_summary: "Summarize Gmail",
                action_count: 1,
                actions: [{ tool: "gmail", label: "Summarize Gmail" }],
                last_run_at: null,
                next_run_at: null,
                last_error: null,
                needs_attention: false,
            },
        ];

        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /workflows/i }));
        const runButton = screen.getByRole("button", { name: /run now/i });

        fireEvent.click(runButton);

        expect(workflowActions.runNow).toHaveBeenCalledWith("workflow-run");
        expect(runButton).toBeDisabled();
        expect(screen.getByText("Running")).toBeInTheDocument();
    });

    it("explains how to create workflows when the tab is empty", () => {
        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /workflows/i }));

        expect(screen.getByText(/summarize Gmail and Slack/i)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /create with ai/i })).toBeInTheDocument();
    });
});
