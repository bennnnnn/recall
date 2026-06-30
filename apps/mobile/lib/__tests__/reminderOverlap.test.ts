import type { GoogleCalendarEvent, Todo } from "@/lib/api";
import {
  REMINDER_OVERLAP_MS,
  buildCalendarOverlapNotes,
  buildReminderOverlapNotes,
  findOverlappingCalendarEvent,
  findOverlappingReminder,
} from "@/lib/reminderOverlap";

function todo(partial: Partial<Todo> & Pick<Todo, "id" | "content">): Todo {
  return {
    topic: "General",
    checked: false,
    due_at: null,
    sort_order: null,
    chat_id: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    ...partial,
  };
}

describe("findOverlappingReminder", () => {
  it("detects reminders within the overlap window", () => {
    const base = new Date("2026-06-27T10:00:00.000Z");
    const nearby = todo({
      id: "1",
      content: "Walk",
      due_at: new Date(base.getTime() + 10 * 60_000).toISOString(),
    });
    const far = todo({
      id: "2",
      content: "Later",
      due_at: new Date(base.getTime() + 60 * 60_000).toISOString(),
    });

    expect(findOverlappingReminder([nearby, far], base)?.id).toBe("1");
    expect(findOverlappingReminder([far], base)).toBeNull();
  });

  it("ignores checked items and self when excluded", () => {
    const due = new Date("2026-06-27T10:00:00.000Z");
    const item = todo({
      id: "1",
      content: "Walk",
      due_at: due.toISOString(),
    });
    expect(
      findOverlappingReminder([item], due, { excludeId: "1" }),
    ).toBeNull();
    expect(
      findOverlappingReminder(
        [todo({ id: "2", content: "Done", due_at: due.toISOString(), checked: true })],
        due,
      ),
    ).toBeNull();
  });
});

describe("buildReminderOverlapNotes", () => {
  it("maps both sides of a pair", () => {
    const t = new Date("2026-06-27T10:00:00.000Z");
    const a = todo({
      id: "a",
      content: "Walk",
      due_at: t.toISOString(),
    });
    const b = todo({
      id: "b",
      content: "Stretch",
      due_at: new Date(t.getTime() + 5 * 60_000).toISOString(),
    });

    const notes = buildReminderOverlapNotes([a, b]);
    expect(notes.get("a")).toBe("Stretch");
    expect(notes.get("b")).toBe("Walk");
  });
});

describe("findOverlappingCalendarEvent", () => {
  it("flags events overlapping the reminder window", () => {
    const due = new Date("2026-06-27T10:00:00.000Z");
    const event: GoogleCalendarEvent = {
      id: "evt",
      title: "Standup",
      start_at: "2026-06-27T09:55:00.000Z",
      end_at: "2026-06-27T10:25:00.000Z",
      all_day: false,
    };

    expect(findOverlappingCalendarEvent([event], due)?.title).toBe("Standup");
  });
});

describe("buildCalendarOverlapNotes", () => {
  it("maps reminder id to conflicting event title", () => {
    const due = new Date("2026-06-27T10:00:00.000Z");
    const reminder = todo({
      id: "r1",
      content: "Walk",
      due_at: due.toISOString(),
    });
    const event: GoogleCalendarEvent = {
      id: "evt",
      title: "Team sync",
      start_at: "2026-06-27T10:05:00.000Z",
      end_at: "2026-06-27T10:30:00.000Z",
      all_day: false,
    };

    const notes = buildCalendarOverlapNotes([reminder], [event]);
    expect(notes.get("r1")).toBe("Team sync");
  });
});

describe("REMINDER_OVERLAP_MS", () => {
  it("is a 15-minute window", () => {
    expect(REMINDER_OVERLAP_MS).toBe(15 * 60 * 1000);
  });
});
