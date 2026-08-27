import { Menu, PanelRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConversations } from "@/features/chat/conversations-context";

interface TopBarProps {
  onOpenSidebar: () => void;
  onOpenArtifacts: () => void;
  artifactCollapsed: boolean;
  onToggleArtifactCollapsed: () => void;
}

export function TopBar({ onOpenSidebar, onOpenArtifacts, artifactCollapsed, onToggleArtifactCollapsed }: TopBarProps) {
  const { sessions, activeSessionId } = useConversations();
  const activeTitle = sessions.find((s) => s.id === activeSessionId)?.title ?? "New conversation";

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border bg-surface px-3 sm:px-4">
      <div className="flex min-w-0 items-center gap-2">
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={onOpenSidebar} aria-label="Open navigation">
          <Menu className="size-4" aria-hidden="true" />
        </Button>
        <p className="truncate text-sm font-medium">{activeTitle}</p>
        <Badge variant="neutral" className="hidden shrink-0 sm:inline-flex">
          Local environment · Ollama
        </Badge>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <Button
          variant="ghost"
          size="icon"
          className="hidden lg:inline-flex"
          onClick={onToggleArtifactCollapsed}
          aria-pressed={!artifactCollapsed}
          aria-label={artifactCollapsed ? "Show artifact panel" : "Hide artifact panel"}
        >
          <PanelRight className="size-4" aria-hidden="true" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={onOpenArtifacts}
          aria-label="Open artifacts panel"
        >
          <PanelRight className="size-4" aria-hidden="true" />
        </Button>
      </div>
    </header>
  );
}
