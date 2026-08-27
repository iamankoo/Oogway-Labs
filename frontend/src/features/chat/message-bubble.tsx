import ReactMarkdown, { type Components } from "react-markdown";

import { SourceCard } from "@/components/ui/source-card";
import type { Message } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Custom element renderers for assistant Markdown. ``react-markdown``
 * never renders raw HTML found in the source text (no ``rehype-raw`` is
 * used here) - untrusted-looking `<script>`/`<img onerror>` etc. in a
 * model response is displayed as inert text, not executed. This is
 * assistant-text rendering only; it is unrelated to the sandboxed
 * artifact renderer Phase 5 will add for untrusted HTML documents.
 */
const markdownComponents: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  h1: ({ children }) => <h3 className="mb-1.5 mt-3 font-serif text-base font-semibold first:mt-0">{children}</h3>,
  h2: ({ children }) => <h3 className="mb-1.5 mt-3 font-serif text-base font-semibold first:mt-0">{children}</h3>,
  h3: ({ children }) => <h4 className="mb-1 mt-2.5 text-sm font-semibold first:mt-0">{children}</h4>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  code: ({ className, children }) => {
    const isBlock = /language-/.test(className ?? "");
    if (isBlock) {
      return (
        <code className={cn("block overflow-x-auto whitespace-pre font-mono text-xs", className)}>{children}</code>
      );
    }
    return (
      <code className="rounded bg-muted-surface px-1 py-0.5 font-mono text-[0.85em]">{children}</code>
    );
  },
  pre: ({ children }) => (
    <pre className="mb-2 overflow-x-auto rounded-md bg-muted-surface p-2.5 last:mb-0">{children}</pre>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="underline decoration-muted underline-offset-2 hover:decoration-current focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {children}
    </a>
  ),
};

/** Renders one message, plus its citation cards when it's a grounded assistant reply (Phase 4). */
export function MessageBubble({ message }: { message: Message }) {
  if (message.role === "system") {
    return (
      <div role="status" className="flex justify-center py-1">
        <span className="rounded-full bg-muted-surface px-3 py-1 text-xs text-muted">{message.content}</span>
      </div>
    );
  }

  const isUser = message.role === "user";

  return (
    <div className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[75%] break-words rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "whitespace-pre-wrap rounded-br-md bg-primary text-primary-foreground"
            : "rounded-bl-md border border-border bg-surface text-foreground",
        )}
      >
        {isUser ? message.content : <ReactMarkdown components={markdownComponents}>{message.content}</ReactMarkdown>}
      </div>
      {message.grounded && (
        <div className="mt-2 flex max-w-[75%] flex-col gap-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Grounded in Lenny's Podcast · {message.sources.length} source
            {message.sources.length === 1 ? "" : "s"}
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {message.sources.map((source) => (
              <SourceCard key={source.source_id} source={source} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
