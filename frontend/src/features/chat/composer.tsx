import { ArrowUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
}

export function Composer({ value, onChange }: ComposerProps) {
  return (
    <div className="shrink-0 border-t border-border bg-surface p-4">
      <div className="mx-auto flex max-w-2xl items-end gap-2 rounded-lg border border-border bg-background p-2 transition-shadow focus-within:ring-2 focus-within:ring-ring">
        <Textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Ask about growth, activation, retention, pricing..."
          rows={1}
          className="max-h-40 min-h-9 flex-1 border-0 bg-transparent shadow-none focus-visible:ring-0"
          aria-label="Message Lenny Growth Assistant"
        />
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={-1}>
              <Button size="icon" disabled aria-label="Send message">
                <ArrowUp className="size-4" aria-hidden="true" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>Sending connects once the agent layer ships in a later phase.</TooltipContent>
        </Tooltip>
      </div>
      <p className="mx-auto mt-2 max-w-2xl text-center text-xs text-muted">
        This preview does not send messages yet. Composer, states, and layout only.
      </p>
    </div>
  );
}
