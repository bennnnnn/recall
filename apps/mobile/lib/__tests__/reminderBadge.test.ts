import type { Todo } from "@/lib/api";
import {
  countUrgentReminders,
  countUnseenUrgentReminders,
  listUrgentReminders,
} from "@/lib/reminderBadge";

function todo(partial: Partial<Todo> & Pick<Todo, "id" | "content">): Todo {
  return {
    topic: "General",
    checked: false,
    due_at: null,
    sort_order: null,
    chat_id: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...partial,
  };
}

const now = new Date("2026-06-27T12:00:00.000Z");
const lead = 15;

describe("reminderBadge urgency (lead-based)", () => {
  it("includes overdue reminders", () => {
    const overdue = todo({ id: "1", content: "Late", due_at: "2026-06-27T10:00:00.000Z" });
    expect(listUrgentReminders([overdue], now, lead).map((t) => t.id)).toEqual(["1"]);
  });

  it("includes reminders due within the lead window", () => {
    const soon = todo({ id: "2", content: "Soon", due_at: "2026-06-27T12:10:00.000Z" });
    expect(countUrgentReminders([soon], now, lead)).toBe(1);
  });

  it("excludes reminders beyond the lead window (not 'later today')", () => {
    // Due 3 hours later same day — old 'later today' rule would have included it.
    const laterToday = todo({ id: "3", content: "Evening", due_at: "2026-06-27T15:00:00.000Z" });
    expect(listUrgentReminders([laterToday], now, lead)).toEqual([]);
  });

  it("excludes checked and undated items", () => {
    const done = todo({ id: "4", content: "Done", due_at: "2026-06-27T12:05:00.000Z", checked: true });
    const undated = todo({ id: "5", content: "Milk" });
    expect(countUrgentReminders([done, undated], now, lead)).toBe(0);
  });

  it("counts only unseen urgent reminders", () => {
    const overdue = todo({ id: "1", content: "Late", due_at: "2026-06-27T10:00:00.000Z" });
    const soon = todo({ id: "2", content: "Soon", due_at: "2026-06-27T12:10:00.000Z" });
    const seen = new Set<string>(["1"]);
    expect(countUnseenUrgentReminders([overdue, soon], seen, now, lead)).toBe(1);
  });
});
