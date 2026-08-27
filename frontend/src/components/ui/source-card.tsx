import { ExternalLink, Mic } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * Visual foundation for a future knowledge-source citation (Phase 4 RAG).
 * Not rendered anywhere in Phase 2 - there is no retrieved source data yet,
 * and this component takes no defaults, so it cannot be used to display
 * fabricated episode/guest content by accident.
 */
export interface SourceCardProps {
  episodeTitle: string;
  guest: string;
  sourceType: "podcast" | "newsletter";
  excerpt: string;
  href: string;
  className?: string;
}

export function SourceCard({ episodeTitle, guest, sourceType, excerpt, href, className }: SourceCardProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={cn(
        "group flex flex-col gap-2 rounded-lg border border-border bg-surface p-3 text-left transition-colors",
        "hover:border-border-strong hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5 text-muted">
          <Mic className="size-3.5 shrink-0" aria-hidden="true" />
          <Badge variant="outline" className="px-1.5 py-0 text-[10px] capitalize">
            {sourceType}
          </Badge>
        </div>
        <ExternalLink
          className="size-3.5 shrink-0 text-muted opacity-0 transition-opacity group-hover:opacity-100"
          aria-hidden="true"
        />
      </div>
      <p className="font-serif text-sm font-medium leading-snug text-foreground">{episodeTitle}</p>
      <p className="text-xs text-muted">{guest}</p>
      <p className="line-clamp-3 border-l-2 border-border pl-2.5 text-xs italic leading-relaxed text-muted">
        “{excerpt}”
      </p>
    </a>
  );
}
