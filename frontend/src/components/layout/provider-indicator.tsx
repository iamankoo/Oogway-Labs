import { useConversations } from "@/features/chat/conversations-context";
import { cn } from "@/lib/utils";

/**
 * Reflects the backend's real active model configuration - fetched from
 * GET /api/provider, never hard-coded. Subtle by design: this answers
 * "which model is answering this?" without dominating the sidebar.
 */
export function ProviderIndicator() {
  const { providerStatus } = useConversations();

  if (!providerStatus) return null;

  const isLocal = providerStatus.provider === "ollama";

  return (
    <div className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted">
      <span
        className={cn("size-1.5 shrink-0 rounded-full", isLocal ? "bg-success" : "bg-primary")}
        aria-hidden="true"
      />
      <span>
        <span className="font-medium text-foreground">{isLocal ? "Local" : "Cloud"}</span>
        {" · "}
        {providerStatus.model}
      </span>
    </div>
  );
}
