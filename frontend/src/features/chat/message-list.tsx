import { AlertCircle, MessageSquareText } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { MessageBubble } from "@/features/chat/message-bubble";
import type { Message } from "@/lib/types";

interface MessageListProps {
  messages: Message[];
  state: "idle" | "loading" | "error";
  error: string | null;
  onRetry: () => void;
}

function MessageListSkeleton() {
  return (
    <div className="flex flex-col gap-3 p-4" aria-hidden="true">
      <Skeleton className="h-12 w-2/3 self-start rounded-2xl" />
      <Skeleton className="h-9 w-1/2 self-end rounded-2xl" />
      <Skeleton className="h-16 w-3/5 self-start rounded-2xl" />
    </div>
  );
}

export function MessageList({ messages, state, error, onRetry }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length]);

  if (state === "loading") {
    return <MessageListSkeleton />;
  }

  if (state === "error") {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Couldn't load this conversation"
        description={error ?? "Something went wrong. Please try again."}
        className="py-16"
        action={
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Try again
          </Button>
        }
      />
    );
  }

  if (messages.length === 0) {
    return (
      <EmptyState
        icon={MessageSquareText}
        title="This conversation is empty"
        description="Send a message below to get started."
        className="py-16"
      />
    );
  }

  return (
    <div role="log" aria-live="polite" className="flex flex-col gap-3 p-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
