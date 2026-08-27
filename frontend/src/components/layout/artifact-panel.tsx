import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";

export function ArtifactPanel() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3.5">
        <div>
          <p className="text-sm font-semibold">Artifacts</p>
          <p className="text-xs text-muted">Plans, frameworks, and documents Lenny produces</p>
        </div>
        <Badge variant="outline" className="shrink-0">
          Later phase
        </Badge>
      </div>
      <EmptyState
        icon={FileText}
        title="No artifacts yet"
        description="When Lenny generates a document, framework, or plan worth keeping, it will open here for review and export."
      />
    </div>
  );
}
