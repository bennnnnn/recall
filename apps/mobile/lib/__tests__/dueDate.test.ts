import { describeDueAt, toDueAtIso } from "@/lib/todos/dueDate";

describe("describeDueAt", () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  function freezeAt(local: Date) {
    jest.useFakeTimers();
    jest.setSystemTime(local);
  }

  it("returns null for missing or invalid values", () => {
    expect(describeDueAt(null)).toBeNull();
    expect(describeDueAt("not-a-date")).toBeNull();
  });

  it("labels an overdue time later the same day", () => {
    freezeAt(new Date(2026, 8, 8, 15, 0, 0));
    const iso = toDueAtIso(new Date(2026, 8, 8, 9, 0, 0));
    expect(describeDueAt(iso)).toEqual({
      label: "Overdue today",
      tone: "overdue",
    });
  });

  it("labels overdue by day count", () => {
    freezeAt(new Date(2026, 8, 8, 12, 0, 0));
    const iso = toDueAtIso(new Date(2026, 8, 5, 9, 0, 0));
    expect(describeDueAt(iso)).toEqual({
      label: "3d overdue",
      tone: "overdue",
    });
  });

  it("labels a later time today", () => {
    freezeAt(new Date(2026, 8, 8, 9, 0, 0));
    const due = new Date(2026, 8, 8, 17, 30, 0);
    const iso = toDueAtIso(due);
    expect(describeDueAt(iso)).toEqual({
      label: `Today ${due.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`,
      tone: "today",
    });
  });

  it("labels tomorrow", () => {
    freezeAt(new Date(2026, 8, 8, 12, 0, 0));
    const iso = toDueAtIso(new Date(2026, 8, 9, 10, 0, 0));
    expect(describeDueAt(iso)).toEqual({
      label: "Tomorrow",
      tone: "soon",
    });
  });
});
