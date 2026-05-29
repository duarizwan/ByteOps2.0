import type { ToolType } from "@/hooks/use-tool-connections";

export interface ToolCapabilityEntry {
    label: string;
    capabilities: string[];
}

export const TOOL_CAPABILITIES: Record<ToolType, ToolCapabilityEntry> = {
    "gmail": {
        label: "Gmail",
        capabilities: [
            "Read and search your emails",
            "Send, reply to, or forward emails",
            "Draft emails for your review",
            "Summarise inbox threads",
        ],
    },
    "calendar": {
        label: "Calendar",
        capabilities: [
            "List upcoming events",
            "Create, update, or delete events",
            "Schedule meetings with natural language",
            "Search events by date or title",
        ],
    },
    "slack": {
        label: "Slack",
        capabilities: [
            "Read channels and messages",
            "Send messages or DMs (with your confirmation)",
            "Search conversations",
            "List workspace users",
        ],
    },
    "jira": {
        label: "Jira",
        capabilities: [
            "Search and list issues with JQL",
            "Create issues (with your confirmation)",
            "Transition issue status",
            "View sprint progress",
        ],
    },
    "github": {
        label: "GitHub",
        capabilities: [
            "List repositories and pull requests",
            "View open issues and notifications",
            "Check PR status and review requests",
        ],
    },
    "dropbox": {
        label: "Dropbox",
        capabilities: [
            "List files and folders",
            "Upload or download files",
            "Move, rename, or delete files (with your confirmation)",
            "Create shared links",
        ],
    },
    "trello": {
        label: "Trello",
        capabilities: [
            "View boards, lists, and cards",
            "Create and move cards",
            "Check due dates and assignments",
        ],
    },
};
