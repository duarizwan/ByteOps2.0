import { describe, it, expect } from "vitest";
import { classifyError } from "@/lib/classify-error";

describe("classifyError", () => {
    // ── Auth errors ────────────────────────────────────────────────────────────
    it("returns 'auth' for error containing '401'", () => {
        expect(classifyError("HTTP 401 Unauthorized")).toBe("auth");
    });

    it("returns 'auth' for error containing '403'", () => {
        expect(classifyError("403 Forbidden")).toBe("auth");
    });

    it("returns 'auth' for error containing 'token'", () => {
        expect(classifyError("Invalid token provided")).toBe("auth");
    });

    it("returns 'auth' for error containing 'expired'", () => {
        expect(classifyError("Session expired, please re-authenticate")).toBe("auth");
    });

    it("returns 'auth' for error containing 'unauthorized' (case-insensitive)", () => {
        expect(classifyError("Unauthorized access")).toBe("auth");
        expect(classifyError("UNAUTHORIZED")).toBe("auth");
    });

    // ── Timeout / API errors ───────────────────────────────────────────────────
    it("returns 'timeout' for error containing 'timeout'", () => {
        expect(classifyError("Request timeout after 30s")).toBe("timeout");
    });

    it("returns 'timeout' for error containing '503'", () => {
        expect(classifyError("503 Service Unavailable")).toBe("timeout");
    });

    it("returns 'timeout' for error containing 'api error' (case-insensitive)", () => {
        expect(classifyError("API error from Slack")).toBe("timeout");
        expect(classifyError("api error: rate limit")).toBe("timeout");
    });

    // ── Unknown / fallback ─────────────────────────────────────────────────────
    it("returns 'unknown' for null error", () => {
        expect(classifyError(null)).toBe("unknown");
    });

    it("returns 'unknown' for empty string", () => {
        expect(classifyError("")).toBe("unknown");
    });

    it("returns 'unknown' for unrecognised error string", () => {
        expect(classifyError("Something went wrong during processing")).toBe("unknown");
    });

    it("returns 'unknown' for generic network error", () => {
        expect(classifyError("Failed to fetch")).toBe("unknown");
    });
});
