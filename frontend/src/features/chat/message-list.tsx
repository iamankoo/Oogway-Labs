import { AlertCircle, MessageSquareText } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { GenerationErrorCard } from "@/features/chat/generation-error-card";
import { MessageBubble } from "@/features/chat/message-bubble";
import { ThinkingIndicator } from "@/features/chat/thinking-indicator";
import type { GenerationError, Message } from "@/lib/types";

interface MessageListProps {
  messages: Message[];
  state: "idle" | "loading" | "error";
  error: string | null;
  onRetryLoad: () => void;
  isGenerating: boolean;
  generationError: GenerationError | null;
  onRetryGeneration: () => void;
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

export function MessageList({
  messages,
  state,
  error,
  onRetryLoad,
  isGenerating,
  generationError,
  onRetryGeneration,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, isGenerating, generationError]);

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
          <Button variant="secondary" size="sm" onClick={onRetryLoad}>
            Try again
          </Button>
        }
      />
    );
  }

  if (messages.length === 0 && !isGenerating && !generationError) {
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
    <div role="log" aria-live="polite" aria-busy={isGenerating} className="flex flex-col gap-3 p-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {isGenerating && <ThinkingIndicator />}
      {generationError && !isGenerating && <GenerationErrorCard error={generationError} onRetry={onRetryGeneration} />}
      <div ref={bottomRef} />
    </div>
  );
}
