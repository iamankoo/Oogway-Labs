import { cn } from "@/lib/utils";

/**
 * A static, decorative waveform glyph - a restrained nod to the product's
 * podcast/interview knowledge base. Deliberately not an animated audio
 * player: it's an icon, not a media control.
 */
export function WaveformIcon({ className }: { className?: string }) {
  const bars = [5, 10, 16, 10, 6, 13, 8];
  return (
    <svg viewBox="0 0 56 20" className={cn("h-5 w-14", className)} aria-hidden="true" focusable="false">
      {bars.map((height, index) => (
        <rect
          key={index}
          x={index * 8}
          y={(20 - height) / 2}
          width={4}
          height={height}
          rx={2}
          fill="currentColor"
        />
      ))}
    </svg>
  );
}
