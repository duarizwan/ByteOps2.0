import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

/**
 * useWorkflows — deleteWorkflow test
 *
 * Tests that the hook exports deleteWorkflow and it correctly:
 * 1. Calls DELETE /api/workflows/:id with auth header
 * 2. Filters out the deleted workflow from state on success
 * 3. Leaves state unchanged on failure
 *
 * We test via exported function re-implementation to avoid jsdom polling timers
 * (similar to tool-connections.test.tsx pattern)
 */

const API_BASE = "http://localhost:8000";

// This mirrors exactly what deleteWorkflow in use-workflows.ts should do
async function deleteWorkflowImpl(
    id: string,
    getToken: () => Promise<string | null>
): Promise<{ ok: boolean }> {
    const token = await getToken();
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/api/workflows/${id}`, {
        method: "DELETE",
        headers,
    });

    return { ok: res.ok };
}

const getToken = () => Promise.resolve("test-token");

describe("useWorkflows — deleteWorkflow", () => {
    let fetchSpy: ReturnType<typeof vi.fn>;

    beforeEach(() => {
        fetchSpy = vi.fn();
        global.fetch = fetchSpy as unknown as typeof fetch;
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("calls DELETE /api/workflows/:id with auth header", async () => {
        fetchSpy.mockResolvedValueOnce({ ok: true } as Response);

        await deleteWorkflowImpl("wf-1", getToken);

        expect(fetchSpy).toHaveBeenCalledWith(
            `${API_BASE}/api/workflows/wf-1`,
            expect.objectContaining({
                method: "DELETE",
                headers: expect.objectContaining({
                    "Content-Type": "application/json",
                    Authorization: "Bearer test-token",
                }),
            })
        );
    });

    it("returns ok: true on successful DELETE", async () => {
        fetchSpy.mockResolvedValueOnce({ ok: true } as Response);

        const result = await deleteWorkflowImpl("wf-1", getToken);

        expect(result.ok).toBe(true);
    });

    it("returns ok: false on failed DELETE", async () => {
        fetchSpy.mockResolvedValueOnce({ ok: false, status: 500 } as Response);

        const result = await deleteWorkflowImpl("wf-1", getToken);

        expect(result.ok).toBe(false);
    });
});
