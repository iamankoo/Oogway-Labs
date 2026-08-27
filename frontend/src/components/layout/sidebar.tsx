import { AlertCircle, BookOpen, MessageSquare, Plus, Settings } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { NavItem } from "@/components/layout/nav-item";
import { ProviderIndicator } from "@/components/layout/provider-indicator";
import { SessionItem } from "@/components/layout/session-item";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { useConversations } from "@/features/chat/conversations-context";
import { groupSessionsByRecency } from "@/lib/session-grouping";

interface SidebarProps {
  onNavigate?: () => void;
}

function SidebarSkeleton() {
  return (
    <div className="space-y-2 px-3" aria-hidden="true">
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-8 w-5/6" />
      <Skeleton className="h-8 w-4/6" />
    </div>
  );
}

export function Sidebar({ onNavigate }: SidebarProps) {
  const {
    sessions,
    sessionsState,
    sessionsError,
    activeSessionId,
    isCreatingSession,
    selectSession,
    createSession,
    retryLoadSessions,
  } = useConversations();

  const handleNewConversation = async () => {
    await createSession();
    onNavigate?.();
  };

  const handleSelect = (sessionId: string) => {
    selectSession(sessionId);
    onNavigate?.();
  };

  const groups = groupSessionsByRecency(sessions);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div
          className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary font-serif text-sm font-semibold text-primary-foreground"
          aria-hidden="true"
        >
          L
        </div>
        <div className="min-w-0 leading-tight">
          <p className="truncate font-serif text-sm font-semibold">Lenny</p>
          <p className="truncate text-xs text-muted">Growth Assistant</p>
        </div>
      </div>

      <div className="px-3">
        <Button
          variant="secondary"
          className="w-full justify-start gap-2"
          onClick={() => void handleNewConversation()}
          disabled={isCreatingSession}
        >
          <Plus className="size-4" aria-hidden="true" />
          New conversation
        </Button>
      </div>

      <nav aria-label="Conversation history" className="mt-6 min-h-0 flex-1 overflow-y-auto scrollbar-thin px-3">
        {sessionsState === "loading" && <SidebarSkeleton />}

        {sessionsState === "error" && (
          <EmptyState
            icon={AlertCircle}
            title="Couldn't load conversations"
            description={sessionsError ?? "Something went wrong."}
            className="py-8"
            action={
              <Button variant="secondary" size="sm" onClick={retryLoadSessions}>
                Try again
              </Button>
            }
          />
        )}

        {sessionsState === "idle" && sessions.length === 0 && (
          <EmptyState
            icon={MessageSquare}
            title="No conversations yet"
            description="Start a new conversation to see it here."
            className="py-8"
          />
        )}

        {sessionsState === "idle" &&
          groups.map((group) => (
            <div key={group.label} className="mb-4">
              <p className="px-2 pb-1.5 text-xs font-medium uppercase tracking-wide text-muted">{group.label}</p>
              <div className="space-y-0.5">
                {group.sessions.map((session) => (
                  <SessionItem
                    key={session.id}
                    session={session}
                    active={session.id === activeSessionId}
                    onSelect={() => handleSelect(session.id)}
                  />
                ))}
              </div>
            </div>
          ))}
      </nav>

      <div className="space-y-1 border-t border-border p-3">
        <NavItem icon={BookOpen} label="Knowledge base" badge="Later phase" disabled />
        <NavItem icon={Settings} label="Settings" badge="Later phase" disabled />
        <ThemeToggle />
        <ProviderIndicator />
      </div>
    </div>
  );
}
