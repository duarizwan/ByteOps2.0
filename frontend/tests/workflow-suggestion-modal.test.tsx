import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { vi, describe, it, expect } from "vitest";

const WORKFLOW_SUGGESTIONS = [
    {
        id: "morning-briefing",
        title: "Morning briefing",
        description: "Every morning, summarize Gmail and Slack, then list anything urgent",
        prompt: "Create a workflow that runs every morning, summarizes my Gmail and Slack messages, and lists anything urgent.",
    },
    {
        id: "meeting-prep",
        title: "Meeting prep",
        description: "Before each calendar event, research the topic and prepare talking points",
        prompt: "Create a workflow that runs before each calendar event to research the topic and prepare talking points.",
    },
    {
        id: "weekly-status",
        title: "Weekly status report",
        description: "Every Friday, summarize completed tasks and draft a team status update",
        prompt: "Create a workflow that runs every Friday, summarizes my completed tasks, and drafts a team status update.",
    },
    {
        id: "slack-mentions",
        title: "Slack mention tracker",
        description: "When Slack messages mention me, summarize and add to my task list",
        prompt: "Create a workflow that runs when Slack messages mention me, summarizes them, and adds action items to my task list.",
    },
    {
        id: "eod-winddown",
        title: "End-of-day wind-down",
        description: "At 5pm, review tomorrow's calendar and send a prep summary to my email",
        prompt: "Create a workflow that runs at 5pm every day, reviews my calendar for tomorrow, and sends a prep summary to my email.",
    },
] as const;

function WorkflowSuggestionModal({
    onClose,
    onSelect,
}: {
    onClose: () => void;
    onSelect: (prompt: string) => void;
}) {
    return (
        <div role="dialog" aria-modal="true" aria-label="Choose a workflow to build">
            <button onClick={onClose} aria-label="Close">Cancel</button>
            {WORKFLOW_SUGGESTIONS.map((s) => (
                <button key={s.id} onClick={() => { onSelect(s.prompt); onClose(); }}>
                    {s.title}
                </button>
            ))}
        </div>
    );
}

describe("WorkflowSuggestionModal", () => {
    it("renders all 5 suggestions", () => {
        render(<WorkflowSuggestionModal onClose={vi.fn()} onSelect={vi.fn()} />);
        expect(screen.getByText("Morning briefing")).toBeInTheDocument();
        expect(screen.getByText("Meeting prep")).toBeInTheDocument();
        expect(screen.getByText("Weekly status report")).toBeInTheDocument();
        expect(screen.getByText("Slack mention tracker")).toBeInTheDocument();
        expect(screen.getByText("End-of-day wind-down")).toBeInTheDocument();
    });

    it("calls onSelect with the correct prompt when a suggestion is clicked", () => {
        const onSelect = vi.fn();
        render(<WorkflowSuggestionModal onClose={vi.fn()} onSelect={onSelect} />);
        fireEvent.click(screen.getByText("Morning briefing"));
        expect(onSelect).toHaveBeenCalledWith(
            "Create a workflow that runs every morning, summarizes my Gmail and Slack messages, and lists anything urgent."
        );
    });

    it("calls onClose when Cancel is clicked", () => {
        const onClose = vi.fn();
        render(<WorkflowSuggestionModal onClose={onClose} onSelect={vi.fn()} />);
        fireEvent.click(screen.getByLabelText("Close"));
        expect(onClose).toHaveBeenCalledOnce();
    });

    it("calls both onSelect and onClose when a suggestion is clicked", () => {
        const onClose = vi.fn();
        const onSelect = vi.fn();
        render(<WorkflowSuggestionModal onClose={onClose} onSelect={onSelect} />);
        fireEvent.click(screen.getByText("Meeting prep"));
        expect(onSelect).toHaveBeenCalledOnce();
        expect(onClose).toHaveBeenCalledOnce();
    });
});
