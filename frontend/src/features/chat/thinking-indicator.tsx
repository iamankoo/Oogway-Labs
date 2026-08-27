import { WaveformIcon } from "@/components/ui/waveform-icon";

/**
 * A restrained "assistant is working" state - communicates progress
 * without exposing any hidden reasoning or internal agent steps.
 */
export function ThinkingIndicator() {
  return (
    <div className="flex justify-start" role="status" aria-live="polite">
      <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-border bg-surface px-4 py-2.5 text-sm text-muted">
        <WaveformIcon className="h-3.5 w-7 animate-pulse text-primary" />
        <span>Thinking through that…</span>
      </div>
    </div>
  );
}
