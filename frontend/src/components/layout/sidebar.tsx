import { BookOpen, MessageSquare, Plus, Settings } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { NavItem } from "@/components/layout/nav-item";
import { ThemeToggle } from "@/components/layout/theme-toggle";

interface SidebarProps {
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div
          className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary text-sm font-semibold text-primary-foreground"
          aria-hidden="true"
        >
          L
        </div>
        <div className="min-w-0 leading-tight">
          <p className="truncate text-sm font-semibold">Lenny</p>
          <p className="truncate text-xs text-muted">Growth Assistant</p>
        </div>
      </div>

      <div className="px-3">
        <Button variant="secondary" className="w-full justify-start gap-2" onClick={onNavigate}>
          <Plus className="size-4" aria-hidden="true" />
          New conversation
        </Button>
      </div>

      <nav aria-label="Conversation history" className="mt-6 min-h-0 flex-1 overflow-y-auto scrollbar-thin px-3">
        <p className="px-2 text-xs font-medium uppercase tracking-wide text-muted">Conversations</p>
        <EmptyState
          icon={MessageSquare}
          title="No conversations yet"
          description="Conversations you start will be listed here."
          className="py-8"
        />
      </nav>

      <div className="space-y-1 border-t border-border p-3">
        <NavItem icon={BookOpen} label="Knowledge base" badge="Later phase" disabled />
        <NavItem icon={Settings} label="Settings" badge="Later phase" disabled />
        <ThemeToggle />
      </div>
    </div>
  );
}
