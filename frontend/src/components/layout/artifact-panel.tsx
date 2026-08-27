import { AlertCircle, Code2, FileText, Loader2, Rocket } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useConversations } from "@/features/chat/conversations-context";
import type { Artifact, ArtifactKind } from "@/lib/types";
import { cn } from "@/lib/utils";

const KIND_META: Record<ArtifactKind, { label: string; icon: typeof Rocket }> = {
  ship30: { label: "Ship 30 Essay", icon: Rocket },
  markdown: { label: "Markdown", icon: FileText },
  html: { label: "HTML page", icon: Code2 },
};

const ACTIONS: { kind: ArtifactKind; label: string }[] = [
  { kind: "ship30", label: "Ship 30 Essay" },
  { kind: "markdown", label: "Markdown doc" },
  { kind: "html", label: "HTML page" },
];

/**
 * Renders a generated HTML artifact in an isolated, script-free frame.
 *
 * Security posture (see docs/architecture.md "Artifact HTML isolation"):
 * generated HTML is untrusted model output, never rendered via
 * `dangerouslySetInnerHTML` in the main app. `sandbox=""` (no tokens at
 * all) applies every restriction the sandbox attribute offers at once:
 * scripts do not run, forms do not submit, popups are blocked, and the
 * frame is given a unique opaque origin - so even if the HTML contained
 * a script, it could not execute, and even if it somehow could, it would
 * have no access to this page's cookies, storage, or DOM. `srcDoc` keeps
 * the content inline with no network request.
 */
function HtmlArtifactFrame({ content }: { content: string }) {
  return (
    <iframe
      title="Generated HTML artifact preview"
      srcDoc={content}
      sandbox=""
      className="h-full w-full rounded-md border border-border bg-white"
    />
  );
}

function ArtifactContent({ artifact }: { artifact: Artifact }) {
  if (artifact.kind === "html") {
    return (
      <div className="flex h-full flex-col gap-2 p-4">
        <HtmlArtifactFrame content={artifact.content} />
      </div>
    );
  }
  return (
    <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin p-4">
      <article className="prose-sm max-w-none text-sm leading-relaxed text-foreground">
        <ReactMarkdown
          components={{
            h1: ({ children }) => <h2 className="mb-3 font-serif text-xl font-semibold">{children}</h2>,
            h2: ({ children }) => <h3 className="mb-2 mt-5 font-serif text-base font-semibold">{children}</h3>,
            h3: ({ children }) => <h4 className="mb-1.5 mt-4 text-sm font-semibold">{children}</h4>,
            p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
            ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-5">{children}</ul>,
            ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-5">{children}</ol>,
            strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          }}
        >
          {artifact.content}
        </ReactMarkdown>
      </article>
    </div>
  );
}

export function ArtifactPanel() {
  const {
    activeSessionId,
    artifacts,
    activeArtifactId,
    selectArtifact,
    isGeneratingArtifact,
    artifactGenerationError,
    generateArtifact,
  } = useConversations();

  const activeArtifact = artifacts.find((a) => a.id === activeArtifactId) ?? artifacts[artifacts.length - 1] ?? null;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3.5">
        <div>
          <p className="text-sm font-semibold">Artifacts</p>
          <p className="text-xs text-muted">Plans, frameworks, and documents Lenny produces</p>
        </div>
      </div>

      {activeSessionId && (
        <div className="flex flex-wrap gap-1.5 border-b border-border px-4 py-3">
          {ACTIONS.map(({ kind, label }) => (
            <Button
              key={kind}
              size="sm"
              variant="secondary"
              disabled={isGeneratingArtifact}
              onClick={() => void generateArtifact(kind)}
            >
              {isGeneratingArtifact ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
              {label}
            </Button>
          ))}
        </div>
      )}

      {artifacts.length > 1 && (
        <div className="flex flex-wrap gap-1.5 border-b border-border px-4 py-2.5">
          {artifacts.map((artifact) => {
            const meta = KIND_META[artifact.kind];
            const Icon = meta.icon;
            return (
              <button
                key={artifact.id}
                type="button"
                onClick={() => selectArtifact(artifact.id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
                  artifact.id === activeArtifact?.id
                    ? "border-primary bg-primary-muted text-primary"
                    : "border-border text-muted hover:bg-accent",
                )}
              >
                <Icon className="size-3" aria-hidden="true" />
                <span className="max-w-[10rem] truncate">{artifact.title}</span>
              </button>
            );
          })}
        </div>
      )}

      {artifactGenerationError && !isGeneratingArtifact && (
        <div className="mx-4 mt-3 flex items-center gap-2 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
          <AlertCircle className="size-3.5 shrink-0" aria-hidden="true" />
          {artifactGenerationError}
        </div>
      )}

      {!activeSessionId ? (
        <EmptyState
          icon={FileText}
          title="No conversation yet"
          description="Start a conversation, then generate a Ship 30 essay or a Markdown/HTML document from it."
        />
      ) : isGeneratingArtifact && !activeArtifact ? (
        <EmptyState
          icon={Loader2}
          title="Generating…"
          description="Drafting your content from this conversation and any relevant Lenny material."
          className="[&_svg]:animate-spin"
        />
      ) : activeArtifact ? (
        <>
          <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
            <Badge variant="outline" className="capitalize">
              {KIND_META[activeArtifact.kind].label}
            </Badge>
            <p className="truncate text-sm font-medium text-foreground">{activeArtifact.title}</p>
          </div>
          <ArtifactContent artifact={activeArtifact} />
        </>
      ) : (
        <EmptyState
          icon={FileText}
          title="No artifacts yet"
          description="Use one of the actions above to turn this conversation into a Ship 30 essay, a Markdown document, or an HTML page."
        />
      )}
    </div>
  );
}
