import { useState } from "react";

import { ArtifactPanel } from "@/components/layout/artifact-panel";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { ChatWorkspace } from "@/features/chat/chat-workspace";

export function AppShell() {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [mobileArtifactsOpen, setMobileArtifactsOpen] = useState(false);
  const [artifactCollapsed, setArtifactCollapsed] = useState(false);

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-background text-foreground">
      <aside className="hidden shrink-0 border-r border-border bg-surface lg:flex lg:w-[272px] lg:flex-col">
        <Sidebar />
      </aside>

      <Dialog open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
        <DialogContent side="left" hideClose className="p-0">
          <DialogTitle className="sr-only">Navigation</DialogTitle>
          <Sidebar onNavigate={() => setMobileSidebarOpen(false)} />
        </DialogContent>
      </Dialog>

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          onOpenSidebar={() => setMobileSidebarOpen(true)}
          onOpenArtifacts={() => setMobileArtifactsOpen(true)}
          artifactCollapsed={artifactCollapsed}
          onToggleArtifactCollapsed={() => setArtifactCollapsed((collapsed) => !collapsed)}
        />
        <div className="flex min-h-0 flex-1">
          <ChatWorkspace className="min-w-0 flex-1" />
          {!artifactCollapsed && (
            <aside className="hidden shrink-0 border-l border-border bg-surface lg:flex lg:w-[360px] lg:flex-col">
              <ArtifactPanel />
            </aside>
          )}
        </div>
      </div>

      <Dialog open={mobileArtifactsOpen} onOpenChange={setMobileArtifactsOpen}>
        <DialogContent side="right" hideClose className="p-0">
          <DialogTitle className="sr-only">Artifacts</DialogTitle>
          <ArtifactPanel />
        </DialogContent>
      </Dialog>
    </div>
  );
}
