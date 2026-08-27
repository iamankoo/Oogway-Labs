import { Sparkles } from "lucide-react";

const SUGGESTED_PROMPTS = [
  "What signals indicate we've found product-market fit?",
  "Help me design an activation experiment for our onboarding funnel.",
  "Critique this pricing page for a B2B SaaS product.",
  "What should our first growth loop look like?",
];

interface WelcomeStateProps {
  onSelectPrompt: (prompt: string) => void;
}

export function WelcomeState({ onSelectPrompt }: WelcomeStateProps) {
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center gap-6 px-6 py-16 text-center">
      <div className="flex size-12 items-center justify-center rounded-xl bg-primary-muted text-primary">
        <Sparkles className="size-6" aria-hidden="true" />
      </div>
      <div className="space-y-2">
        <h1 className="text-xl font-semibold tracking-tight">Ask Lenny about growth, product, and onboarding</h1>
        <p className="text-sm text-muted">
          Grounded in interviews and essays from Lenny Rachitsky&apos;s newsletter and podcast. Answers will be
          traceable back to source material once retrieval is connected in a later phase.
        </p>
      </div>
      <div className="grid w-full gap-2 sm:grid-cols-2">
        {SUGGESTED_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onSelectPrompt(prompt)}
            className="rounded-lg border border-border bg-surface p-3 text-left text-sm text-foreground transition-colors hover:border-border-strong hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
