/**
 * ByteOps API client — fetch wrapper with Clerk JWT injection.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FetchOptions extends RequestInit {
    /** If true, include Clerk session token in Authorization header. */
    auth?: boolean;
}

async function _authHeaders(): Promise<Record<string, string>> {
    if (typeof window === "undefined") return {};
    try {
        // @ts-expect-error - Clerk exposes session on window in client
        const token = await window?.Clerk?.session?.getToken();
        return token ? { Authorization: `Bearer ${token}` } : {};
    } catch {
        return {};
    }
}

/**
 * Make an authenticated API request to the ByteOps backend.
 *
 * @example
 * const data = await api("/api/conversations", { auth: true });
 */
export async function api<T = unknown>(
    path: string,
    options: FetchOptions = {},
): Promise<T> {
    const { auth = true, headers: customHeaders, ...rest } = options;

    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(customHeaders as Record<string, string>),
        ...(auth ? await _authHeaders() : {}),
    };

    const response = await fetch(`${API_BASE}${path}`, { headers, ...rest });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText || `HTTP ${response.status}` }));
        throw new Error(error.detail || `API error: ${response.status}`);
    }

    // Handle 204 No Content
    if (response.status === 204) return undefined as T;

    return response.json();
}

/**
 * Make an authenticated SSE streaming request to the ByteOps backend.
 * Throws if the backend returns a non-2xx status before the stream begins.
 */
export async function apiStream(
    path: string,
    body: unknown,
): Promise<Response> {
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(await _authHeaders()),
    };

    const response = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText || `HTTP ${response.status}` }));
        throw new Error(error.detail || `Stream error: ${response.status}`);
    }

    return response;
}
