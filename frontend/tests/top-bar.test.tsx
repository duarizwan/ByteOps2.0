import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import React from "react";

vi.mock("@clerk/nextjs", () => ({ UserButton: () => null }));
vi.mock("next/link", () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}));
vi.mock("@/components/theme-provider", () => ({
    useTheme: () => ({ resolvedTheme: "dark", setTheme: vi.fn(), theme: "dark" }),
}));

import { TopBar } from "@/components/dashboard/top-bar";

describe("TopBar", () => {
    it("renders subtitle without duplicate ByteOps", () => {
        render(<TopBar />);
        expect(screen.getByText("AI Work Assistant")).toBeInTheDocument();
        expect(screen.queryByText(/AI Work Assistant · ByteOps/)).not.toBeInTheDocument();
    });

    it("does not render the plain text b logo span", () => {
        render(<TopBar />);
        const spans = document.querySelectorAll("span");
        const bSpan = Array.from(spans).find(
            (s) => s.textContent === "b" && s.tagName === "SPAN"
        );
        expect(bSpan).toBeUndefined();
    });
});
