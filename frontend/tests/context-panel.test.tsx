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
        status: "active" | "paused" | "running" | "failed";
        trigger_label: string;
        action_summary: string;
        last_run_at: string | null;
        next_run_at: string | null;
        last_error: string | null;
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
        pause: vi.fn(),
        resume: vi.fn(),
        runNow: vi.fn(),
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
    });

    it("tab label spans use hidden lg:inline, not hidden xl:inline", () => {
        const { container } = render(<ContextPanel {...props} />);
        const xlSpans = container.querySelectorAll(".hidden.xl\\:inline");
        expect(xlSpans).toHaveLength(0);
        const lgSpans = container.querySelectorAll(".hidden.lg\\:inline");
        expect(lgSpans.length).toBeGreaterThan(0);
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
                content: "- Review | contract *terms* today.",
                priority: "high",
                is_read: false,
                created_at: "2026-05-29T10:00:00.000Z",
                metadata: { category: "alert" },
            },
        ];

        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /tasks/i }));

        expect(screen.getByText("CFO contract update")).toBeInTheDocument();
        expect(screen.getByText("Review contract terms today.")).toBeInTheDocument();
        expect(screen.queryByText("*CFO* | contract - update")).not.toBeInTheDocument();
        expect(screen.queryByText("- Review | contract *terms* today.")).not.toBeInTheDocument();
    });

    it("renders workflow cards with status, trigger, actions, and clean errors", () => {
        workflowState.workflows = [
            {
                id: "workflow-1",
                name: "Daily inbox triage",
                description: "Summarize important emails each morning.",
                status: "active",
                trigger_label: "Every weekday at 9:00 AM",
                action_summary: "Summarize unread important emails",
                last_run_at: "2026-05-29T09:00:00.000Z",
                next_run_at: "2026-05-30T09:00:00.000Z",
                last_error: null,
            },
            {
                id: "workflow-2",
                name: "Slack follow-up monitor",
                description: null,
                status: "failed",
                trigger_label: "Manual run",
                action_summary: "Find unanswered mentions",
                last_run_at: null,
                next_run_at: null,
                last_error: "Slack | token - expired",
            },
        ];

        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /workflows/i }));

        expect(screen.getByText("Daily inbox triage")).toBeInTheDocument();
        expect(screen.getByText("Active")).toBeInTheDocument();
        expect(screen.getByText("Every weekday at 9:00 AM")).toBeInTheDocument();
        expect(screen.getByText("Summarize unread important emails")).toBeInTheDocument();
        expect(screen.getByText("Slack follow up monitor")).toBeInTheDocument();
        expect(screen.getByText("Failed")).toBeInTheDocument();
        expect(screen.getByText("Slack token expired")).toBeInTheDocument();
        expect(screen.queryByText("Workflows coming soon")).not.toBeInTheDocument();
    });
});
