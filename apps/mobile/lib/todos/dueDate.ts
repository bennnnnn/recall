export type DueTone = "overdue" | "today" | "soon" | "later";

export function describeDueAt(iso: string | null | undefined): {
  label: string;
  tone: DueTone;
} | null {
  if (!iso) return null;
  const due = new Date(iso);
  if (Number.isNaN(due.getTime())) return null;

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfDue = new Date(due.getFullYear(), due.getMonth(), due.getDate());
  const dayDiff = Math.round(
    (startOfDue.getTime() - startOfToday.getTime()) / (24 * 60 * 60 * 1000),
  );

  if (due.getTime() < now.getTime()) {
    if (dayDiff === 0) return { label: "Overdue today", tone: "overdue" };
    const days = Math.max(1, Math.abs(dayDiff));
    return { label: `${days}d overdue`, tone: "overdue" };
  }
  if (dayDiff === 0) {
    return {
      label: `Today ${due.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`,
      tone: "today",
    };
  }
  if (dayDiff === 1) return { label: "Tomorrow", tone: "soon" };
  if (dayDiff <= 7) {
    return {
      label: due.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }),
      tone: "soon",
    };
  }
  return {
    label: due.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }),
    tone: "later",
  };
}

export function toDueAtIso(date: Date): string {
  return date.toISOString();
}
