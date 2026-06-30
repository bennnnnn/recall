import type { Todo } from "@/lib/api";
import {
  DEFAULT_HOME_URGENT_LEAD,
  homeUrgentPrompt,
  homeUrgentSubtitle,
  listHomeUrgentTodos,
  partitionHomeUrgentTodos,
} from "@/lib/homeUrgentTodos";

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

describe("listHomeUrgentTodos", () => {
  const now = new Date("2026-06-27T12:00:00.000Z");
  // Use a 30-min lead so the "due soon" fixtures (30 min ahead) are urgent.
  const lead = 30;

  it("includes overdue reminders in the urgent window", () => {
    const overdue = todo({
      id: "1",
      content: "Pay rent",
      due_at: "2026-06-26T12:00:00.000Z",
    });

    const urgent = listHomeUrgentTodos([overdue], now, lead);
    expect(urgent.map((item) => item.id)).toEqual(["1"]);
    expect(urgent[0].minutes_until).toBeLessThan(0);
  });

  it("partitions overdue and upcoming", () => {
    const overdue = todo({
      id: "1",
      content: "Late",
      due_at: "2026-06-26T12:00:00.000Z",
    });
    const dueSoon = todo({
      id: "2",
      content: "Soon",
      due_at: "2026-06-27T12:30:00.000Z",
    });
    const { overdue: o, dueSoon: s } = partitionHomeUrgentTodos(
      listHomeUrgentTodos([overdue, dueSoon], now, lead),
    );
    expect(o.map((item) => item.id)).toEqual(["1"]);
    expect(s.map((item) => item.id)).toEqual(["2"]);
  });

  it("includes reminders due within the lead window", () => {
    const dueSoon = todo({
      id: "1",
      content: "Pay rent",
      due_at: "2026-06-27T12:30:00.000Z",
    });
    const later = todo({
      id: "2",
      content: "Later",
      due_at: "2026-06-27T14:00:00.000Z",
    });

    const urgent = listHomeUrgentTodos([dueSoon, later], now, lead);
    expect(urgent.map((item) => item.id)).toEqual(["1"]);
  });

  it("excludes items beyond the lead window", () => {
    const tooFar = todo({
      id: "9",
      content: "Far",
      due_at: "2026-06-27T12:45:00.000Z", // 45 min ahead, lead is 30
    });
    expect(listHomeUrgentTodos([tooFar], now, lead)).toEqual([]);
  });

  it("excludes checked items and list items without due dates", () => {
    const done = todo({
      id: "1",
      content: "Done",
      due_at: "2026-06-27T12:15:00.000Z",
      checked: true,
    });
    const listItem = todo({ id: "2", content: "Milk" });

    expect(listHomeUrgentTodos([done, listItem], now, lead)).toEqual([]);
  });

  it("limits to five soonest items", () => {
    const items = Array.from({ length: 7 }, (_, index) =>
      todo({
        id: String(index),
        content: `Task ${index}`,
        due_at: new Date(now.getTime() + (index + 1) * 60_000).toISOString(),
      }),
    );

    expect(listHomeUrgentTodos(items, now, lead)).toHaveLength(5);
  });

  it("defaults to the shared default lead when none provided", () => {
    const dueAt = new Date(now.getTime() + (DEFAULT_HOME_URGENT_LEAD - 1) * 60_000).toISOString();
    const justInside = todo({ id: "1", content: "Soon", due_at: dueAt });
    expect(listHomeUrgentTodos([justInside], now)).toHaveLength(1);
  });
});

describe("homeUrgentSubtitle", () => {
  it("returns null when empty", () => {
    expect(homeUrgentSubtitle([])).toBeNull();
  });

  it("describes multiple overdue reminders", () => {
    expect(
      homeUrgentSubtitle([
        {
          id: "1",
          content: "A",
          topic: "General",
          due_at: "2026-06-26T12:00:00.000Z",
          minutes_until: -60,
        },
        {
          id: "2",
          content: "B",
          topic: "General",
          due_at: "2026-06-26T11:00:00.000Z",
          minutes_until: -120,
        },
      ]),
    ).toBe("2 reminders overdue.");
  });

  it("uses overdue prompt text", () => {
    expect(
      homeUrgentPrompt({
        id: "1",
        content: "D",
        topic: "General",
        due_at: "2026-06-26T12:00:00.000Z",
        minutes_until: -1440,
      }),
    ).toContain("overdue");
  });
});
