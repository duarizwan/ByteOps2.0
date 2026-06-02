import { renderHook, act, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";

// Use a stable getToken reference so the useCallback([getToken]) in the hook
// does not create a new fetch_ function on every render (which would cause an
// infinite re-render loop via the useEffect([fetch_]) dependency).
const stableGetToken = async () => "test-token";

vi.mock("@clerk/nextjs", () => ({
    useAuth: () => ({ getToken: stableGetToken }),
}));

const mockWorkflows = [
    { id: "wf-1", name: "Morning Briefing", status: "active", trigger: {}, actions: [], trigger_label: "daily", condition_summary: "", action_summary: "", action_count: 1, last_run_at: null, next_run_at: null, last_error: null, description: null },
    { id: "wf-2", name: "Weekly Report", status: "paused", trigger: {}, actions: [], trigger_label: "weekly", condition_summary: "", action_summary: "", action_count: 1, last_run_at: null, next_run_at: null, last_error: null, description: null },
];

describe("useWorkflows — deleteWorkflow", () => {
    beforeEach(() => {
        vi.stubGlobal("fetch", vi.fn());
    });

    afterEach(() => {
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it("removes the workflow from state on successful DELETE", async () => {
        const { useWorkflows } = await import("../src/hooks/use-workflows");
        const fetchMock = vi.mocked(fetch);
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => mockWorkflows,
        } as Response);
        fetchMock.mockResolvedValueOnce({ ok: true } as Response);

        const { result } = renderHook(() => useWorkflows());

        await waitFor(() => {
            expect(result.current.workflows).toHaveLength(2);
        });

        await act(async () => {
            await result.current.deleteWorkflow("wf-1");
        });

        expect(result.current.workflows).toHaveLength(1);
        expect(result.current.workflows[0].id).toBe("wf-2");
    });

    it("calls DELETE /api/workflows/:id with auth header", async () => {
        const { useWorkflows } = await import("../src/hooks/use-workflows");
        const fetchMock = vi.mocked(fetch);
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => mockWorkflows,
        } as Response);
        fetchMock.mockResolvedValueOnce({ ok: true } as Response);

        const { result } = renderHook(() => useWorkflows());

        await waitFor(() => {
            expect(result.current.workflows).toHaveLength(2);
        });

        await act(async () => {
            await result.current.deleteWorkflow("wf-1");
        });

        // The DELETE call is whichever call has method: "DELETE"
        const deleteCall = fetchMock.mock.calls.find(
            ([, init]) => (init as RequestInit)?.method === "DELETE"
        );
        expect(deleteCall).toBeDefined();
        const [url, init] = deleteCall!;
        expect(String(url)).toContain("/api/workflows/wf-1");
        expect((init as RequestInit).method).toBe("DELETE");
        expect(
            ((init as RequestInit).headers as Record<string, string>)["Authorization"]
        ).toBe("Bearer test-token");
    });

    it("does not change state when DELETE fails", async () => {
        const { useWorkflows } = await import("../src/hooks/use-workflows");
        const fetchMock = vi.mocked(fetch);
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => mockWorkflows,
        } as Response);
        fetchMock.mockResolvedValueOnce({ ok: false, status: 500 } as Response);

        const { result } = renderHook(() => useWorkflows());

        await waitFor(() => {
            expect(result.current.workflows).toHaveLength(2);
        });

        await act(async () => {
            await result.current.deleteWorkflow("wf-1");
        });

        expect(result.current.workflows).toHaveLength(2);
    });
});
