import { render } from "@testing-library/react";
import { vi } from "vitest";
import React from "react";

vi.mock("next/link", () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}));
vi.mock("@/hooks/use-tool-connections", () => ({
    useToolConnections: () => ({ isConnected: (id: string) => id === "gmail" }),
}));
vi.mock("@/lib/brand-icons", () => ({ getBrandIconUrl: () => null }));
vi.mock("@/hooks/use-conversations", () => ({ ConversationSummary: {} }));

import { CollapsibleSidebar } from "@/components/dashboard/collapsible-sidebar";

const baseProps = {
    isCollapsed: false,
    onToggleCollapse: vi.fn(),
    conversations: [],
    isLoadingConversations: false,
    activeConversationId: null,
    onNewChat: vi.fn(),
    onSelectConversation: vi.fn(),
    onDeleteConversation: vi.fn().mockResolvedValue(true),
};

describe("CollapsibleSidebar", () => {
    it("applies glow shadow class to connected tool dot", () => {
        const { container } = render(<CollapsibleSidebar {...baseProps} />);
        const glowDots = container.querySelectorAll('[class*="shadow-"]');
        expect(glowDots.length).toBeGreaterThan(0);
    });

    it("conversation list does not have max-h-64 class", () => {
        const { container } = render(<CollapsibleSidebar {...baseProps} />);
        const maxHEl = container.querySelector(".max-h-64");
        expect(maxHEl).not.toBeInTheDocument();
    });
});
