import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { api, ApiError } from "@/lib/api";
import type { Message, Session } from "@/lib/types";

const ACTIVE_SESSION_STORAGE_KEY = "lenny-active-session-id";

type LoadState = "idle" | "loading" | "error";

interface ConversationsState {
  sessions: Session[];
  sessionsState: LoadState;
  sessionsError: string | null;
  activeSessionId: string | null;
  messages: Message[];
  messagesState: LoadState;
  messagesError: string | null;
  isCreatingSession: boolean;
  isSendingMessage: boolean;
  selectSession: (sessionId: string) => void;
  createSession: () => Promise<void>;
  /** Sends to the active session, creating one first if none is active yet. */
  sendMessage: (content: string) => Promise<void>;
  retryLoadSessions: () => void;
  retryLoadMessages: () => void;
}

const ConversationsContext = createContext<ConversationsState | null>(null);

function readStoredActiveSessionId(): string | null {
  try {
    return window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeActiveSessionId(sessionId: string | null): void {
  try {
    if (sessionId) {
      window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, sessionId);
    } else {
      window.localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
    }
  } catch {
    // Best-effort convenience only - a private browsing session or a
    // cleared store just means the active conversation isn't restored.
  }
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

function sortByRecency(sessions: Session[]): Session[] {
  return [...sessions].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

export function ConversationsProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionsState, setSessionsState] = useState<LoadState>("loading");
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [sessionsReloadToken, setSessionsReloadToken] = useState(0);

  const [activeSessionId, setActiveSessionId] = useState<string | null>(readStoredActiveSessionId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messagesState, setMessagesState] = useState<LoadState>("idle");
  const [messagesError, setMessagesError] = useState<string | null>(null);
  const [messagesReloadToken, setMessagesReloadToken] = useState(0);

  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isSendingMessage, setIsSendingMessage] = useState(false);

  // A brand-new session is known to have zero messages - skip the network
  // round-trip for it so a message sent immediately after creation can't
  // race with (and be wiped out by) that fetch resolving afterwards.
  const skipNextMessagesFetch = useRef(false);

  useEffect(() => {
    let cancelled = false;
    setSessionsState("loading");
    setSessionsError(null);

    api
      .listSessions()
      .then((result) => {
        if (cancelled) return;
        setSessions(result);
        setSessionsState("idle");
        setActiveSessionId((current) => {
          if (current && result.some((s) => s.id === current)) return current;
          return result[0]?.id ?? null;
        });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setSessionsError(errorMessage(error));
        setSessionsState("error");
      });

    return () => {
      cancelled = true;
    };
  }, [sessionsReloadToken]);

  useEffect(() => {
    storeActiveSessionId(activeSessionId);

    if (!activeSessionId) {
      setMessages([]);
      setMessagesState("idle");
      return;
    }

    if (skipNextMessagesFetch.current) {
      skipNextMessagesFetch.current = false;
      setMessages([]);
      setMessagesState("idle");
      return;
    }

    let cancelled = false;
    setMessages([]);
    setMessagesState("loading");
    setMessagesError(null);

    api
      .listMessages(activeSessionId)
      .then((result) => {
        if (cancelled) return;
        setMessages(result);
        setMessagesState("idle");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setMessagesError(errorMessage(error));
        setMessagesState("error");
      });

    return () => {
      cancelled = true;
    };
  }, [activeSessionId, messagesReloadToken]);

  const selectSession = useCallback((sessionId: string) => {
    setActiveSessionId(sessionId);
  }, []);

  const createAndActivateSession = useCallback(async (): Promise<Session> => {
    const session = await api.createSession();
    setSessions((current) => [session, ...current]);
    skipNextMessagesFetch.current = true;
    setActiveSessionId(session.id);
    return session;
  }, []);

  const createSession = useCallback(async () => {
    setIsCreatingSession(true);
    try {
      await createAndActivateSession();
    } finally {
      setIsCreatingSession(false);
    }
  }, [createAndActivateSession]);

  const sendMessageToSession = useCallback(async (sessionId: string, content: string) => {
    const result = await api.sendMessage(sessionId, content);
    setMessages((current) => [...current, result.message]);
    setSessions((current) => sortByRecency(current.map((s) => (s.id === result.session.id ? result.session : s))));
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      setIsSendingMessage(true);
      try {
        const sessionId = activeSessionId ?? (await createAndActivateSession()).id;
        await sendMessageToSession(sessionId, content);
      } finally {
        setIsSendingMessage(false);
      }
    },
    [activeSessionId, createAndActivateSession, sendMessageToSession],
  );

  const retryLoadSessions = useCallback(() => setSessionsReloadToken((t) => t + 1), []);
  const retryLoadMessages = useCallback(() => setMessagesReloadToken((t) => t + 1), []);

  const value = useMemo<ConversationsState>(
    () => ({
      sessions,
      sessionsState,
      sessionsError,
      activeSessionId,
      messages,
      messagesState,
      messagesError,
      isCreatingSession,
      isSendingMessage,
      selectSession,
      createSession,
      sendMessage,
      retryLoadSessions,
      retryLoadMessages,
    }),
    [
      sessions,
      sessionsState,
      sessionsError,
      activeSessionId,
      messages,
      messagesState,
      messagesError,
      isCreatingSession,
      isSendingMessage,
      selectSession,
      createSession,
      sendMessage,
      retryLoadSessions,
      retryLoadMessages,
    ],
  );

  return <ConversationsContext.Provider value={value}>{children}</ConversationsContext.Provider>;
}

export function useConversations(): ConversationsState {
  const context = useContext(ConversationsContext);
  if (!context) {
    throw new Error("useConversations must be used within a ConversationsProvider");
  }
  return context;
}
