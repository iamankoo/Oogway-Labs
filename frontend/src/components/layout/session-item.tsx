import { formatSessionTimestamp } from "@/lib/session-grouping";
import type { Session } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SessionItemProps {
  session: Session;
  active: boolean;
  onSelect: () => void;
}

export function SessionItem({ session, active, onSelect }: SessionItemProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={active ? "true" : undefined}
      className={cn(
        "group flex w-full items-center gap-2 rounded-md border-l-2 px-2.5 py-2 text-left text-sm transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "border-primary bg-primary-muted text-primary"
          : "border-transparent text-foreground hover:bg-accent",
      )}
    >
      <span className="min-w-0 flex-1 truncate">{session.title}</span>
      <span className={cn("shrink-0 text-[11px]", active ? "text-primary/70" : "text-muted")}>
        {formatSessionTimestamp(session.updated_at)}
      </span>
    </button>
  );
}
