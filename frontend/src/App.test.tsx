import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { ApiError } from "@/lib/api";
import type { Message, ProviderStatus, Session } from "@/lib/types";

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    listSessions: vi.fn(),
    createSession: vi.fn(),
    getSession: vi.fn(),
    listMessages: vi.fn(),
    sendMessage: vi.fn(),
    retryMessage: vi.fn(),
    getProviderStatus: vi.fn(),
  },
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: mockApi };
});

function makeSession(overrides: Partial<Session> = {}): Session {
  return {
    id: "session-1",
    title: "New conversation",
    created_at: "2026-08-27T10:00:00Z",
    updated_at: "2026-08-27T10:00:00Z",
    ...overrides,
  };
}

function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: "message-1",
    session_id: "session-1",
    role: "user",
    content: "hello",
    created_at: "2026-08-27T10:00:01Z",
    ...overrides,
  };
}

function makeProviderStatus(overrides: Partial<ProviderStatus> = {}): ProviderStatus {
  return { provider: "ollama", model: "llama3.2:3b", ...overrides };
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  mockApi.getProviderStatus.mockResolvedValue(makeProviderStatus());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("empty state", () => {
  it("shows the product-specific welcome copy and suggested prompts when there are no sessions", async () => {
    mockApi.listSessions.mockResolvedValue([]);

    render(<App />);

    expect(await screen.findByText(/no conversations yet/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /product thinking, growth, and leadership/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /what makes a strong product onboarding/i })).toBeInTheDocument();
  });

  it("fills the composer without sending when a suggested prompt is clicked", async () => {
    mockApi.listSessions.mockResolvedValue([]);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText(/no conversations yet/i);
    await user.click(screen.getByRole("button", { name: /help me reason through a product decision/i }));

    expect(screen.getByLabelText(/message lenny growth assistant/i)).toHaveValue(
      "Help me reason through a product decision",
    );
    expect(mockApi.createSession).not.toHaveBeenCalled();
  });
});

describe("provider indicator", () => {
  it("reflects the backend's real active configuration", async () => {
    mockApi.listSessions.mockResolvedValue([]);
    render(<App />);

    expect(await screen.findByText(/local/i)).toBeInTheDocument();
    expect(screen.getByText(/llama3\.2:3b/)).toBeInTheDocument();
  });

  it("shows a cloud provider when the backend is configured for one", async () => {
    mockApi.listSessions.mockResolvedValue([]);
    mockApi.getProviderStatus.mockResolvedValue(makeProviderStatus({ provider: "cloud", model: "claude-opus-5" }));
    render(<App />);

    expect(await screen.findByText(/cloud/i)).toBeInTheDocument();
    expect(screen.getByText(/claude-opus-5/)).toBeInTheDocument();
  });
});

describe("sidebar session list", () => {
  it("renders existing sessions and marks the restored one active", async () => {
    const sessionA = makeSession({ id: "a", title: "Growth loops" });
    const sessionB = makeSession({ id: "b", title: "Onboarding audit" });
    mockApi.listSessions.mockResolvedValue([sessionA, sessionB]);
    mockApi.listMessages.mockResolvedValue([]);

    render(<App />);

    const sidebar = await screen.findByRole("navigation", { name: /conversation history/i });
    expect(await within(sidebar).findByText("Growth loops")).toBeInTheDocument();
    expect(within(sidebar).getByText("Onboarding audit")).toBeInTheDocument();
  });

  it("shows an error state with retry when loading sessions fails", async () => {
    mockApi.listSessions.mockRejectedValueOnce(new ApiError("The service is unavailable.", "internal_error", 500));
    mockApi.listSessions.mockResolvedValueOnce([]);
    const user = userEvent.setup();

    render(<App />);

    expect(await screen.findByText(/couldn't load conversations/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(mockApi.listSessions).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/no conversations yet/i)).toBeInTheDocument();
  });
});

describe("composer and message flow", () => {
  it("creates a session, sends a message, and renders both turns", async () => {
    const created = makeSession({ id: "new-session" });
    mockApi.listSessions.mockResolvedValue([]);
    mockApi.createSession.mockResolvedValue(created);
    const userMsg = makeMessage({ session_id: "new-session", content: "What is PMF?" });
    const assistantMsg = makeMessage({
      id: "message-2",
      session_id: "new-session",
      role: "assistant",
      content: "Product-market fit means...",
    });
    mockApi.sendMessage.mockResolvedValue({
      message: userMsg,
      assistant_message: assistantMsg,
      session: { ...created, title: "What is PMF?" },
      generation_error: null,
    });
    const user = userEvent.setup();

    render(<App />);
    await screen.findByText(/no conversations yet/i);

    const textbox = screen.getByLabelText(/message lenny growth assistant/i);
    await user.type(textbox, "What is PMF?");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => expect(mockApi.createSession).toHaveBeenCalledTimes(1));
    expect(mockApi.sendMessage).toHaveBeenCalledWith("new-session", "What is PMF?");
    const conversationLog = await screen.findByRole("log");
    expect(await within(conversationLog).findByText("What is PMF?")).toBeInTheDocument();
    expect(within(conversationLog).getByText("Product-market fit means...")).toBeInTheDocument();
    expect(textbox).toHaveValue("");
  });

  it("renders assistant Markdown safely without executing raw HTML", async () => {
    const session = makeSession();
    mockApi.listSessions.mockResolvedValue([session]);
    mockApi.listMessages.mockResolvedValue([
      makeMessage({
        role: "assistant",
        content: "## Key point\n\n- **Bold** idea\n- <img src=x onerror=alert(1)>\n\nSee `code` here.",
      }),
    ]);

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Key point", level: 3 })).toBeInTheDocument();
    expect(screen.getByText("Bold").tagName).toBe("STRONG");
    expect(screen.getByText("code").tagName).toBe("CODE");
    expect(document.querySelector("img")).not.toBeInTheDocument();
  });

  it("shows a thinking indicator while generating and replaces it with the reply", async () => {
    const session = makeSession();
    mockApi.listSessions.mockResolvedValue([session]);
    mockApi.listMessages.mockResolvedValue([]);
    let resolveSend!: (value: unknown) => void;
    mockApi.sendMessage.mockReturnValue(new Promise((resolve) => (resolveSend = resolve)));
    const user = userEvent.setup();

    render(<App />);
    const textbox = await screen.findByLabelText(/message lenny growth assistant/i);
    await user.type(textbox, "hello");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    expect(await screen.findByText(/thinking through that/i)).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument(); // shown immediately, not just once the reply lands

    resolveSend({
      message: makeMessage({ content: "hello" }),
      assistant_message: makeMessage({ id: "m2", role: "assistant", content: "Hi there" }),
      session,
      generation_error: null,
    });

    expect(await screen.findByText("Hi there")).toBeInTheDocument();
    expect(screen.queryByText(/thinking through that/i)).not.toBeInTheDocument();
  });

  it("keeps the user message and shows a retry affordance when generation fails", async () => {
    const session = makeSession();
    mockApi.listSessions.mockResolvedValue([session]);
    mockApi.listMessages.mockResolvedValue([]);
    mockApi.sendMessage.mockResolvedValue({
      message: makeMessage({ content: "hello" }),
      assistant_message: null,
      session,
      generation_error: { code: "provider_unavailable", message: "Local model unavailable." },
    });
    mockApi.retryMessage.mockResolvedValue({
      assistant_message: makeMessage({ id: "m2", role: "assistant", content: "Recovered answer" }),
      session,
      generation_error: null,
    });
    const user = userEvent.setup();

    render(<App />);
    const textbox = await screen.findByLabelText(/message lenny growth assistant/i);
    await user.type(textbox, "hello");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    expect(await screen.findByText("hello")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent(/local model unavailable/i);

    await user.click(screen.getByRole("button", { name: /try again/i }));

    expect(await screen.findByText("Recovered answer")).toBeInTheDocument();
    expect(mockApi.retryMessage).toHaveBeenCalledWith(session.id);
    expect(mockApi.sendMessage).toHaveBeenCalledTimes(1); // retry never resends the user message
  });

  it("shows an inline error and restores the draft when the send request itself fails", async () => {
    const session = makeSession();
    mockApi.listSessions.mockResolvedValue([session]);
    mockApi.listMessages.mockResolvedValue([]);
    mockApi.sendMessage.mockRejectedValue(new ApiError("Couldn't reach the server.", "network_error", 0));
    const user = userEvent.setup();

    render(<App />);
    const textbox = await screen.findByLabelText(/message lenny growth assistant/i);
    await user.type(textbox, "hello there");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn't be sent/i);
    expect(textbox).toHaveValue("hello there");
  });

  it("shows the empty-conversation state for a session with no messages", async () => {
    const session = makeSession();
    mockApi.listSessions.mockResolvedValue([session]);
    mockApi.listMessages.mockResolvedValue([]);

    render(<App />);

    expect(await screen.findByText(/this conversation is empty/i)).toBeInTheDocument();
  });

  it("keeps messages isolated when switching between two sessions", async () => {
    const sessionA = makeSession({ id: "a", title: "Session A" });
    const sessionB = makeSession({ id: "b", title: "Session B" });
    mockApi.listSessions.mockResolvedValue([sessionA, sessionB]);
    mockApi.listMessages.mockImplementation((sessionId: string) =>
      Promise.resolve(
        sessionId === "a"
          ? [makeMessage({ id: "m-a", session_id: "a", content: "message in A" })]
          : [makeMessage({ id: "m-b", session_id: "b", content: "message in B" })],
      ),
    );
    const user = userEvent.setup();

    render(<App />);
    const sidebar = await screen.findByRole("navigation", { name: /conversation history/i });
    await within(sidebar).findByText("Session A");

    expect(await screen.findByText("message in A")).toBeInTheDocument();
    expect(screen.queryByText("message in B")).not.toBeInTheDocument();

    await user.click(within(sidebar).getByText("Session B"));

    expect(await screen.findByText("message in B")).toBeInTheDocument();
    expect(screen.queryByText("message in A")).not.toBeInTheDocument();
  });
});
