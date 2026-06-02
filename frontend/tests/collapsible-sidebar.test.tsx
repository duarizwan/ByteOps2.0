import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import React from "react";

vi.mock("next/link", () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}));
vi.mock("@/hooks/use-tool-connections", () => ({
    useToolConnections: () => ({
        isConnected: (id: string) => id === "gmail",
        initiateConnect: vi.fn(),
        disconnect: vi.fn(),
        connectViaApiKey: vi.fn(),
    }),
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

describe("ConnectToolModal", () => {
    it("opens modal with API Key tab active by default", async () => {
        const { container } = render(<CollapsibleSidebar {...baseProps} />);
        const btn = Array.from(container.querySelectorAll("button")).find(b => b.textContent?.includes("Connect New Tool"));
        expect(btn).toBeTruthy();
        fireEvent.click(btn!);
        expect(screen.getByText("API Key")).toBeTruthy();
        expect(screen.getByText("OAuth")).toBeTruthy();
    });

    it("shows per-tool fields when GitHub chip is selected", async () => {
        const { container } = render(<CollapsibleSidebar {...baseProps} />);
        const btn = Array.from(container.querySelectorAll("button")).find(b => b.textContent?.includes("Connect New Tool"));
        fireEvent.click(btn!);
        // The chip button contains "G" (fallback icon letter) + "GitHub" text since getBrandIconUrl is mocked to null
        const githubChip = Array.from(container.querySelectorAll("button")).find(
            b => b.textContent?.includes("GitHub") && b.classList.contains("rounded-full")
        );
        expect(githubChip).toBeTruthy();
        fireEvent.click(githubChip!);
        expect(screen.getByPlaceholderText(/ghp_/)).toBeTruthy();
    });

    it("shows OAuth tab content when OAuth tab is clicked", async () => {
        const { container } = render(<CollapsibleSidebar {...baseProps} />);
        const btn = Array.from(container.querySelectorAll("button")).find(b => b.textContent?.includes("Connect New Tool"));
        fireEvent.click(btn!);
        const oauthTab = screen.getByText("OAuth");
        fireEvent.click(oauthTab);
        expect(screen.getByText("Select a tool to connect via OAuth")).toBeTruthy();
    });
});
