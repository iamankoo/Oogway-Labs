import { useState } from "react";

import { Composer } from "@/features/chat/composer";
import { WelcomeState } from "@/features/chat/welcome-state";
import { cn } from "@/lib/utils";

interface ChatWorkspaceProps {
  className?: string;
}

export function ChatWorkspace({ className }: ChatWorkspaceProps) {
  const [draft, setDraft] = useState("");

  return (
    <div className={cn("flex flex-col", className)}>
      <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
        <WelcomeState onSelectPrompt={setDraft} />
      </div>
      <Composer value={draft} onChange={setDraft} />
    </div>
  );
}
