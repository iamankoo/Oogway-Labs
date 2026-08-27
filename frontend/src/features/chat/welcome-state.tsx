import { WaveformIcon } from "@/components/ui/waveform-icon";

const SUGGESTED_PROMPTS = [
  "What makes a strong product onboarding experience?",
  "How should I think about product-market fit?",
  "What are common growth mistakes?",
  "Help me reason through a product decision",
];

interface WelcomeStateProps {
  onSelectPrompt: (prompt: string) => void;
}

export function WelcomeState({ onSelectPrompt }: WelcomeStateProps) {
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center gap-6 px-6 py-16 text-center">
      <div className="flex size-12 items-center justify-center rounded-xl bg-primary-muted text-primary">
        <WaveformIcon className="h-5 w-8" />
      </div>
      <div className="space-y-2">
        <h1 className="font-serif text-2xl font-medium tracking-tight text-foreground">
          Product thinking, growth, and leadership - in conversation
        </h1>
        <p className="text-sm text-muted">
          Explore how experienced product leaders reason through onboarding, growth, and hard product
          decisions. Ask a question below to start a conversation - grounded answers from real interviews
          arrive once retrieval is connected in a later phase.
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
