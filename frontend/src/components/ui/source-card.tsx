import { ExternalLink, Mic, Newspaper } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Source } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * A real citation for a grounded assistant answer (Phase 4 RAG). Every
 * field comes straight from `Source` (the API's own retrieval-backed
 * shape) - never a default or placeholder, so this component cannot be
 * used to display fabricated episode/guest/URL content by accident.
 * `guest` and `source_url` are nullable because the underlying source
 * repository doesn't provide them for every entry (e.g. a newsletter
 * post has no guest; some podcast episodes have no post/YouTube URL) -
 * when `source_url` is null, no link is rendered at all.
 */
/** Strips the transcript's own "**Speaker**: " markdown-bold speaker prefix for clean plain-text display. */
function cleanExcerpt(text: string): string {
  return text.replace(/\*\*/g, "").replace(/\n\n/g, " ");
}

export function SourceCard({ source, className }: { source: Source; className?: string }) {
  const byline = [source.title, source.guest].filter(Boolean).join(" — ");
  const Icon = source.source_type === "podcast" ? Mic : Newspaper;

  const content = (
    <>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5 text-muted">
          <Icon className="size-3.5 shrink-0" aria-hidden="true" />
          <Badge variant="outline" className="px-1.5 py-0 text-[10px] capitalize">
            {source.source_type}
          </Badge>
        </div>
        {source.source_url && (
          <ExternalLink
            className="size-3.5 shrink-0 text-muted opacity-0 transition-opacity group-hover:opacity-100"
            aria-hidden="true"
          />
        )}
      </div>
      <p className="font-serif text-sm font-medium leading-snug text-foreground">{source.title}</p>
      {source.guest && <p className="text-xs text-muted">{source.guest}</p>}
      <p className="line-clamp-3 border-l-2 border-border pl-2.5 text-xs italic leading-relaxed text-muted">
        “{cleanExcerpt(source.excerpt)}”
      </p>
    </>
  );

  const classes = cn(
    "group flex flex-col gap-2 rounded-lg border border-border bg-surface p-3 text-left transition-colors",
    source.source_url && "hover:border-border-strong hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    className,
  );

  if (!source.source_url) {
    // No link fabricated when the source repository didn't provide one -
    // shown as a plain (non-interactive) card instead of an <a>.
    return (
      <div className={classes} aria-label={byline}>
        {content}
      </div>
    );
  }

  return (
    <a href={source.source_url} target="_blank" rel="noreferrer" className={classes} aria-label={byline}>
      {content}
    </a>
  );
}
