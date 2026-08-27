import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { ApiError } from "@/lib/api";
import type { Message, Session } from "@/lib/types";

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    listSessions: vi.fn(),
    createSession: vi.fn(),
    getSession: vi.fn(),
    listMessages: vi.fn(),
    sendMessage: vi.fn(),
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

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
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
  it("creates a session and sends the first message, rendering it in the conversation", async () => {
    const created = makeSession({ id: "new-session" });
    mockApi.listSessions.mockResolvedValue([]);
    mockApi.createSession.mockResolvedValue(created);
    const sentMessage = makeMessage({ session_id: "new-session", content: "What is PMF?" });
    mockApi.sendMessage.mockResolvedValue({
      message: sentMessage,
      session: { ...created, title: "What is PMF?" },
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
    expect(textbox).toHaveValue("");
  });

  it("shows an inline error and restores the draft when sending fails", async () => {
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
