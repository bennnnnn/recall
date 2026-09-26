import type { Todo } from "@/lib/api";
import {
  REMINDER_OVERLAP_MS,
  buildReminderOverlapNotes,
  clashClusters,
  findOverlappingReminder,
  groupBySameTime,
} from "@/features/todos/model/reminderOverlap";

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

describe("clashClusters", () => {
  it("groups a same-time pair and skips a later to-do", () => {
    const at = new Date("2026-06-27T14:00:00.000Z");
    const clusters = clashClusters([
      todo({ id: "a", content: "Reading", due_at: at.toISOString() }),
      todo({ id: "b", content: "Walk", due_at: new Date(at.getTime() + 5 * 60_000).toISOString() }),
      todo({ id: "c", content: "Later", due_at: new Date(at.getTime() + 60 * 60_000).toISOString() }),
      todo({ id: "d", content: "Done", due_at: at.toISOString(), checked: true }),
    ]);
    expect(clusters).toEqual([{ names: ["Reading", "Walk"], at: at.toISOString() }]);
  });

  it("joins a chain inside the window and keeps a separate pair apart", () => {
    const first = new Date("2026-06-27T14:00:00.000Z");
    const clusters = clashClusters([
      todo({ id: "a", content: "Reading", due_at: first.toISOString() }),
      todo({ id: "b", content: "Walk", due_at: new Date(first.getTime() + 10 * 60_000).toISOString() }),
      todo({ id: "c", content: "Call", due_at: new Date(first.getTime() + 20 * 60_000).toISOString() }),
      todo({ id: "d", content: "Gym", due_at: new Date(first.getTime() + 3 * 60 * 60_000).toISOString() }),
      todo({ id: "e", content: "Shop", due_at: new Date(first.getTime() + 3 * 60 * 60_000 + 5 * 60_000).toISOString() }),
    ]);
    expect(clusters.map((cluster) => cluster.names)).toEqual([
      ["Reading", "Walk", "Call"],
      ["Gym", "Shop"],
    ]);
  });
});

describe("groupBySameTime", () => {
  it("keeps a same-time pair together and splits a later clock", () => {
    const at = new Date("2026-06-27T14:00:00.000Z");
    const groups = groupBySameTime([
      todo({ id: "a", content: "Reading", due_at: at.toISOString() }),
      todo({ id: "b", content: "Walk", due_at: new Date(at.getTime() + 5 * 60_000).toISOString() }),
      todo({ id: "c", content: "Later", due_at: new Date(at.getTime() + 60 * 60_000).toISOString() }),
    ]);
    expect(groups.map((group) => group.map((item) => item.id))).toEqual([["a", "b"], ["c"]]);
  });

  it("gives every completed to-do its own card", () => {
    const at = new Date("2026-06-27T14:00:00.000Z");
    const groups = groupBySameTime([
      todo({ id: "a", content: "Done", due_at: at.toISOString(), checked: true }),
      todo({ id: "b", content: "Also", due_at: at.toISOString(), checked: true }),
    ]);
    expect(groups).toHaveLength(2);
  });
});

describe("REMINDER_OVERLAP_MS", () => {
  it("is a 15-minute window", () => {
    expect(REMINDER_OVERLAP_MS).toBe(15 * 60 * 1000);
  });
});
