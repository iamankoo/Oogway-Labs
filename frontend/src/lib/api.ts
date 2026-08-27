import { config } from "@/lib/config";
import type { Message, MessageCreateResponse, ProviderStatus, RetryResponse, Session } from "@/lib/types";

/**
 * Thrown for any non-2xx API response. Carries the backend's safe,
 * user-facing message (from the shared error envelope) rather than raw
 * response internals.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${config.apiBaseUrl}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("Couldn't reach the server. Check your connection and try again.", "network_error", 0);
  }

  if (!response.ok) {
    let code = "http_error";
    let message = "Something went wrong. Please try again.";
    try {
      const body = await response.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
    } catch {
      // Response wasn't JSON (e.g. a proxy error page) - fall back to the generic message above.
    }
    throw new ApiError(message, code, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  listSessions: () => request<Session[]>("/api/sessions"),
  createSession: () => request<Session>("/api/sessions", { method: "POST" }),
  getSession: (sessionId: string) => request<Session>(`/api/sessions/${sessionId}`),
  listMessages: (sessionId: string) => request<Message[]>(`/api/sessions/${sessionId}/messages`),
  sendMessage: (sessionId: string, content: string) =>
    request<MessageCreateResponse>(`/api/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ role: "user", content }),
    }),
  retryMessage: (sessionId: string) =>
    request<RetryResponse>(`/api/sessions/${sessionId}/messages/retry`, { method: "POST" }),
  getProviderStatus: () => request<ProviderStatus>("/api/provider"),
};
