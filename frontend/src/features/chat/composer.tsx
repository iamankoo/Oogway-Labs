import { ArrowUp, Loader2 } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (content: string) => Promise<void>;
  sending: boolean;
}

export function Composer({ value, onChange, onSend, sending }: ComposerProps) {
  const [sendError, setSendError] = useState<string | null>(null);
  const canSend = value.trim().length > 0 && !sending;

  const handleSend = async () => {
    if (!canSend) return;
    const content = value.trim();
    setSendError(null);
    try {
      onChange("");
      await onSend(content);
    } catch {
      onChange(content);
      setSendError("Your message couldn't be sent. Please try again.");
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="shrink-0 border-t border-border bg-surface p-4">
      <div className="mx-auto flex max-w-2xl items-end gap-2 rounded-lg border border-border bg-background p-2 transition-shadow focus-within:ring-2 focus-within:ring-ring">
        <Textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about growth, activation, retention, pricing..."
          rows={1}
          disabled={sending}
          className="max-h-40 min-h-9 flex-1 border-0 bg-transparent shadow-none focus-visible:ring-0"
          aria-label="Message Lenny Growth Assistant"
        />
        <Button size="icon" disabled={!canSend} onClick={() => void handleSend()} aria-label="Send message">
          {sending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <ArrowUp className="size-4" />}
        </Button>
      </div>
      <p className="mx-auto mt-2 max-w-2xl text-center text-xs text-muted" role={sendError ? "alert" : undefined}>
        {sendError ?? "Your message is saved to this conversation. Assistant replies arrive in a later phase."}
      </p>
    </div>
  );
}
