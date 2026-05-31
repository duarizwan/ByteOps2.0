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
const agentRunState = vi.hoisted(() => ({
    runs: [] as Array<{
        id: string;
        intent: string;
        status: "planning" | "waiting_approval" | "running" | "completed" | "failed" | "cancelled";
        plan: Record<string, unknown> | null;
        final_response: string | null;
        error: string | null;
        created_at: string;
        updated_at: string;
        completed_at: string | null;
        steps: Array<{
            id: string;
            step_type: "route" | "plan" | "tool_call" | "approval" | "verify" | "final";
            name: string;
            status: string;
            input: Record<string, unknown> | null;
            output: Record<string, unknown> | null;
            error: string | null;
            created_at: string;
        }>;
    }>,
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
vi.mock("@/hooks/use-agent-runs", () => ({
    useAgentRuns: () => ({
        runs: agentRunState.runs,
        isLoading: false,
        refresh: vi.fn(),
    }),
}));
vi.mock("@/lib/brand-icons", () => ({ getBrandIconUrl: () => null }));

import { ContextPanel } from "@/components/dashboard/context-panel";

const props = {
    isCollapsed: false,
    onToggleCollapse: vi.fn(),
};

// Activity tab was removed from ContextPanel (PHR-036, 2026-05-30)
describe.skip("ContextPanel — Activity tab", () => {
    beforeEach(() => {
        notificationState.notifications = [];
        workflowState.workflows = [];
        workflowState.isLoading = false;
        agentRunState.runs = [];
    });

    it("Activity tab shows empty state when no runs", () => {
        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /activity/i }));
        expect(screen.getByText("No activity yet")).toBeInTheDocument();
    });

    it("Activity tab shows completed run intent", () => {
        agentRunState.runs = [
            {
                id: "run-1",
                intent: "check gmail for unread messages",
                status: "completed",
                plan: null,
                final_response: "Found 3 unread emails.",
                error: null,
                created_at: "2026-05-30T10:00:00.000Z",
                updated_at: "2026-05-30T10:01:00.000Z",
                completed_at: "2026-05-30T10:01:00.000Z",
                steps: [],
            },
        ];

        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /activity/i }));

        expect(screen.getByText(/gmail/i)).toBeInTheDocument();
    });

    it("Activity tab shows waiting_approval run", () => {
        agentRunState.runs = [
            {
                id: "run-2",
                intent: "send slack message to team",
                status: "waiting_approval",
                plan: null,
                final_response: null,
                error: null,
                created_at: "2026-05-30T10:05:00.000Z",
                updated_at: "2026-05-30T10:05:00.000Z",
                completed_at: null,
                steps: [
                    {
                        id: "step-1",
                        step_type: "approval",
                        name: "Approve send message",
                        status: "pending",
                        input: null,
                        output: null,
                        error: null,
                        created_at: "2026-05-30T10:05:00.000Z",
                    },
                ],
            },
        ];

        render(<ContextPanel {...props} />);
        fireEvent.click(screen.getByRole("button", { name: /activity/i }));

        // Render succeeds — the run card for the waiting_approval run is present
        expect(screen.getByText(/send slack message to team/i)).toBeInTheDocument();
    });
});
