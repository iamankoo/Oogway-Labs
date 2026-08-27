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
import type { GenerationError, Message, ProviderStatus, Session } from "@/lib/types";

const ACTIVE_SESSION_STORAGE_KEY = "lenny-active-session-id";

type LoadState = "idle" | "loading" | "error";

interface PendingGenerationError {
  sessionId: string;
  error: GenerationError;
}

interface ConversationsState {
  sessions: Session[];
  sessionsState: LoadState;
  sessionsError: string | null;
  activeSessionId: string | null;
  messages: Message[];
  messagesState: LoadState;
  messagesError: string | null;
  isCreatingSession: boolean;
  /** True while the active session is awaiting an assistant reply. */
  isGenerating: boolean;
  generationError: PendingGenerationError | null;
  providerStatus: ProviderStatus | null;
  selectSession: (sessionId: string) => void;
  createSession: () => Promise<void>;
  /** Sends to the active session, creating one first if none is active yet. */
  sendMessage: (content: string) => Promise<void>;
  retryGeneration: () => Promise<void>;
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
  const [pendingSessionId, setPendingSessionId] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<PendingGenerationError | null>(null);
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null);

  // A brand-new session is known to have zero messages - skip the network
  // round-trip for it so a message sent immediately after creation can't
  // race with (and be wiped out by) that fetch resolving afterwards.
  const skipNextMessagesFetch = useRef(false);
  // Read inside async callbacks to detect "the user switched sessions while
  // a request was in flight" - a stale response must never be applied to
  // whatever session is active by the time it resolves.
  const activeSessionIdRef = useRef(activeSessionId);
  activeSessionIdRef.current = activeSessionId;

  useEffect(() => {
    api
      .getProviderStatus()
      .then(setProviderStatus)
      .catch(() => setProviderStatus(null));
  }, []);

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
    setGenerationError(null);

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

  const applySessionUpdate = useCallback((session: Session) => {
    setSessions((current) => sortByRecency(current.map((s) => (s.id === session.id ? session : s))));
  }, []);

  const sendMessageToSession = useCallback(
    async (sessionId: string, content: string) => {
      // Shown immediately so the user sees their own message land while
      // the (potentially slow, CPU-bound local model) reply generates -
      // without this, the transcript looks empty/unresponsive for the
      // entire round trip. Replaced with the server's real message (same
      // content, real id) once the request resolves, or removed if the
      // request itself failed (the composer restores the draft in that case).
      const optimisticId = `optimistic-${Date.now()}`;
      const optimisticMessage: Message = {
        id: optimisticId,
        session_id: sessionId,
        role: "user",
        content,
        created_at: new Date().toISOString(),
        sources: [],
        grounded: false,
      };
      if (activeSessionIdRef.current === sessionId) {
        setMessages((current) => [...current, optimisticMessage]);
      }

      setPendingSessionId(sessionId);
      setGenerationError(null);
      try {
        const result = await api.sendMessage(sessionId, content);
        if (activeSessionIdRef.current !== sessionId) return;

        setMessages((current) => [
          ...current.filter((m) => m.id !== optimisticId),
          result.message,
          ...(result.assistant_message ? [result.assistant_message] : []),
        ]);
        applySessionUpdate(result.session);
        if (result.generation_error) {
          setGenerationError({ sessionId, error: result.generation_error });
        }
      } catch (error) {
        if (activeSessionIdRef.current === sessionId) {
          setMessages((current) => current.filter((m) => m.id !== optimisticId));
        }
        throw error;
      } finally {
        if (activeSessionIdRef.current === sessionId) {
          setPendingSessionId(null);
        }
      }
    },
    [applySessionUpdate],
  );

  const sendMessage = useCallback(
    async (content: string) => {
      const sessionId = activeSessionId ?? (await createAndActivateSession()).id;
      await sendMessageToSession(sessionId, content);
    },
    [activeSessionId, createAndActivateSession, sendMessageToSession],
  );

  const retryGeneration = useCallback(async () => {
    const sessionId = activeSessionId;
    if (!sessionId) return;
    setPendingSessionId(sessionId);
    setGenerationError(null);
    try {
      const result = await api.retryMessage(sessionId);
      if (activeSessionIdRef.current !== sessionId) return;

      if (result.assistant_message) {
        setMessages((current) => [...current, result.assistant_message!]);
      }
      applySessionUpdate(result.session);
      if (result.generation_error) {
        setGenerationError({ sessionId, error: result.generation_error });
      }
    } finally {
      if (activeSessionIdRef.current === sessionId) {
        setPendingSessionId(null);
      }
    }
  }, [activeSessionId, applySessionUpdate]);

  const retryLoadSessions = useCallback(() => setSessionsReloadToken((t) => t + 1), []);
  const retryLoadMessages = useCallback(() => setMessagesReloadToken((t) => t + 1), []);

  const isGenerating = pendingSessionId !== null && pendingSessionId === activeSessionId;

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
      isGenerating,
      generationError: generationError && generationError.sessionId === activeSessionId ? generationError : null,
      providerStatus,
      selectSession,
      createSession,
      sendMessage,
      retryGeneration,
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
      isGenerating,
      generationError,
      providerStatus,
      selectSession,
      createSession,
      sendMessage,
      retryGeneration,
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
