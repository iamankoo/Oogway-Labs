import { useState } from "react";

import { Composer } from "@/features/chat/composer";
import { useConversations } from "@/features/chat/conversations-context";
import { MessageList } from "@/features/chat/message-list";
import { WelcomeState } from "@/features/chat/welcome-state";
import { cn } from "@/lib/utils";

interface ChatWorkspaceProps {
  className?: string;
}

export function ChatWorkspace({ className }: ChatWorkspaceProps) {
  const [draft, setDraft] = useState("");
  const { activeSessionId, messages, messagesState, messagesError, isSendingMessage, sendMessage, retryLoadMessages } =
    useConversations();

  return (
    <div className={cn("flex flex-col", className)}>
      <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
        {activeSessionId ? (
          <MessageList messages={messages} state={messagesState} error={messagesError} onRetry={retryLoadMessages} />
        ) : (
          <WelcomeState onSelectPrompt={setDraft} />
        )}
      </div>
      <Composer value={draft} onChange={setDraft} onSend={sendMessage} sending={isSendingMessage} />
    </div>
  );
}
