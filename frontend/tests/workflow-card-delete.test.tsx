import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { vi, describe, it, expect } from "vitest";

function WorkflowCardDeleteTest({ onDelete }: { onDelete: () => void }) {
    const [confirmDelete, setConfirmDelete] = React.useState(false);

    const handleDeleteClick = () => {
        if (confirmDelete) {
            onDelete();
        } else {
            setConfirmDelete(true);
        }
    };

    React.useEffect(() => {
        if (!confirmDelete) return;
        const handler = (e: MouseEvent) => {
            const btn = document.getElementById("delete-btn");
            if (btn && !btn.contains(e.target as Node)) setConfirmDelete(false);
        };
        document.addEventListener("mousedown", handler);
        return () => document.removeEventListener("mousedown", handler);
    }, [confirmDelete]);

    return (
        <button
            id="delete-btn"
            onClick={handleDeleteClick}
            data-testid="delete-btn"
            className={confirmDelete ? "text-destructive" : ""}
        >
            {confirmDelete ? "Confirm delete?" : "Delete"}
        </button>
    );
}

describe("WorkflowCard — delete inline confirm", () => {
    it("shows 'Delete' initially", () => {
        render(<WorkflowCardDeleteTest onDelete={vi.fn()} />);
        expect(screen.getByText("Delete")).toBeInTheDocument();
    });

    it("first click changes label to 'Confirm delete?'", () => {
        render(<WorkflowCardDeleteTest onDelete={vi.fn()} />);
        fireEvent.click(screen.getByTestId("delete-btn"));
        expect(screen.getByText("Confirm delete?")).toBeInTheDocument();
    });

    it("second click calls onDelete", () => {
        const onDelete = vi.fn();
        render(<WorkflowCardDeleteTest onDelete={onDelete} />);
        fireEvent.click(screen.getByTestId("delete-btn"));
        fireEvent.click(screen.getByTestId("delete-btn"));
        expect(onDelete).toHaveBeenCalledOnce();
    });

    it("clicking outside resets back to 'Delete'", () => {
        render(
            <div>
                <WorkflowCardDeleteTest onDelete={vi.fn()} />
                <div data-testid="outside">outside</div>
            </div>
        );
        fireEvent.click(screen.getByTestId("delete-btn"));
        expect(screen.getByText("Confirm delete?")).toBeInTheDocument();
        fireEvent.mouseDown(screen.getByTestId("outside"));
        expect(screen.getByText("Delete")).toBeInTheDocument();
    });
});
