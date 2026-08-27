import type { Message } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Renders one message. Built to support all three roles now so that
 * Phase 3's assistant responses (and later, source cards under an
 * assistant bubble) slot in without a rework - but Phase 2 only ever
 * passes role="user" messages, since there is no model wired up yet.
 */
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
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[75%] whitespace-pre-wrap break-words rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "rounded-br-md bg-primary text-primary-foreground"
            : "rounded-bl-md border border-border bg-surface text-foreground",
        )}
      >
        {message.content}
      </div>
    </div>
  );
}
