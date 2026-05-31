import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FilterTabs } from "@/components/runs/filter-tabs";

describe("FilterTabs", () => {
    it("renders three tab buttons: All, Pending, Failed", () => {
        render(<FilterTabs active="all" onChange={vi.fn()} />);
        expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Pending" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Failed" })).toBeInTheDocument();
    });

    it("active tab has aria-selected=true", () => {
        render(<FilterTabs active="pending" onChange={vi.fn()} />);
        expect(screen.getByRole("button", { name: "Pending" })).toHaveAttribute("aria-selected", "true");
        expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-selected", "false");
    });

    it("clicking All tab calls onChange with 'all'", () => {
        const onChange = vi.fn();
        render(<FilterTabs active="pending" onChange={onChange} />);
        fireEvent.click(screen.getByRole("button", { name: "All" }));
        expect(onChange).toHaveBeenCalledWith("all");
    });

    it("clicking Pending tab calls onChange with 'pending'", () => {
        const onChange = vi.fn();
        render(<FilterTabs active="all" onChange={onChange} />);
        fireEvent.click(screen.getByRole("button", { name: "Pending" }));
        expect(onChange).toHaveBeenCalledWith("pending");
    });

    it("clicking Failed tab calls onChange with 'failed'", () => {
        const onChange = vi.fn();
        render(<FilterTabs active="all" onChange={onChange} />);
        fireEvent.click(screen.getByRole("button", { name: "Failed" }));
        expect(onChange).toHaveBeenCalledWith("failed");
    });
});
