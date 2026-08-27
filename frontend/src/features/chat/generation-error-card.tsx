import { RefreshCw, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { GenerationError } from "@/lib/types";

interface GenerationErrorCardProps {
  error: GenerationError;
  onRetry: () => void;
}

/**
 * Shown in place of the assistant's reply when generation failed. The
 * user's own message above this is untouched and was already saved -
 * this only ever offers to retry generating the answer, never to resend
 * the question. While a retry is in flight, the caller shows a
 * ``ThinkingIndicator`` instead of this card (see MessageList), so there
 * is no separate "retrying" state to represent here.
 */
export function GenerationErrorCard({ error, onRetry }: GenerationErrorCardProps) {
  return (
    <div className="flex justify-start">
      <div
        role="alert"
        className="flex max-w-[75%] items-start gap-2.5 rounded-2xl rounded-bl-md border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-foreground"
      >
        <TriangleAlert className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden="true" />
        <div className="space-y-2">
          <p>{error.message}</p>
          <Button variant="secondary" size="sm" onClick={onRetry} className="gap-1.5">
            <RefreshCw className="size-3.5" aria-hidden="true" />
            Try again
          </Button>
        </div>
      </div>
    </div>
  );
}
