import type { Session } from "@/lib/types";

export type SessionGroupLabel = "Today" | "Yesterday" | "Earlier";

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function groupLabelFor(dateIso: string, now: Date): SessionGroupLabel {
  const date = new Date(dateIso);
  if (isSameDay(date, now)) return "Today";
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (isSameDay(date, yesterday)) return "Yesterday";
  return "Earlier";
}

/** Buckets sessions (already sorted by recency) into Today / Yesterday / Earlier. */
export function groupSessionsByRecency(
  sessions: Session[],
  now: Date = new Date(),
): { label: SessionGroupLabel; sessions: Session[] }[] {
  const order: SessionGroupLabel[] = ["Today", "Yesterday", "Earlier"];
  const buckets = new Map<SessionGroupLabel, Session[]>();

  for (const session of sessions) {
    const label = groupLabelFor(session.updated_at, now);
    const bucket = buckets.get(label) ?? [];
    bucket.push(session);
    buckets.set(label, bucket);
  }

  return order
    .filter((label) => buckets.has(label))
    .map((label) => ({ label, sessions: buckets.get(label)! }));
}

export function formatSessionTimestamp(dateIso: string, now: Date = new Date()): string {
  const date = new Date(dateIso);
  if (isSameDay(date, now)) {
    return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  }
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
