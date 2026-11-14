import type { ComponentProps } from "react";
import { act, fireEvent, render } from "@testing-library/react-native";

import { TodosScrollList } from "@/features/todos/components/TodosScrollList";
import { buildTodoListRows } from "@/features/todos/model/todoListRows";
import type { Todo } from "@/lib/api";

type Cell = { kind: string; section?: string; todos?: Todo[] };
const mockCells: Cell[][] = [];
const mockScroll = jest.fn();

// The shared stand-in, which draws every cell, keeping the cells it was given and
// answering scrollToIndex through its ref.
jest.mock("@shopify/flash-list", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  return {
    FlashList: ({ ref, data, renderItem, keyExtractor, ListHeaderComponent, ListFooterComponent }: {
      ref?: React.Ref<unknown>;
      data: Cell[];
      renderItem: (info: { item: Cell; index: number }) => React.ReactNode;
      keyExtractor: (item: Cell) => string;
      ListHeaderComponent?: React.ReactNode;
      ListFooterComponent?: React.ReactNode;
    }) => {
      React.useImperativeHandle(ref, () => ({ scrollToIndex: mockScroll }));
      mockCells.push(data);
      return React.createElement(React.Fragment, null, ListHeaderComponent ?? null, ...data.map((item, index) =>
        React.createElement(React.Fragment, { key: keyExtractor(item) }, renderItem({ item, index }))),
      ListFooterComponent ?? null);
    },
  };
});
jest.mock("react-native-gesture-handler/ReanimatedSwipeable", () => {
  const { View } = jest.requireActual("react-native");
  return { __esModule: true, default: View };
});
jest.mock("@/lib/haptics", () => ({ selection: jest.fn() }));

const NOW = new Date(2026, 9, 25, 8);

function todo(id: string, due: Date | null, content = id): Todo {
  return {
    id, content, topic: "General", checked: false, due_at: due?.toISOString() ?? null, recurrence_rule: null,
    sort_order: null, chat_id: null, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
  } as Todo;
}

/** Completed at `updatedAt`: the latest first. */
function done(id: string, due: Date | null, content: string, updatedAt: string): Todo {
  return { ...todo(id, due, content), checked: true, updated_at: updatedAt };
}

type ListProps = Partial<ComponentProps<typeof TodosScrollList>>;

function element(todos: Todo[], props: ListProps = {}) {
  const noop = jest.fn();
  return (
    <TodosScrollList rows={buildTodoListRows(todos, NOW)} now={NOW} error={false} listHeader={<></>}
      busyTodoIds={new Set()} onToggle={noop} onOpen={noop} onDeleteItem={noop}
      completedOpen={false} onToggleCompleted={noop} {...props} />
  );
}

function list(todos: Todo[], props: ListProps = {}) {
  return render(element(todos, props));
}

/** The last cells drawn: a heading by its section, a card by its to-dos. */
function cells(): string[] {
  return mockCells.at(-1)!.map((cell) =>
    cell.kind === "card" ? cell.todos!.map((t) => t.id).join("+") : `# ${cell.section}`);
}

/** One of each section, done ones last. */
const EVERY_SECTION = [
  todo("anytime", null, "Buy milk"),
  done("done", new Date(2026, 9, 24, 9), "Pay rent", "2026-10-24T10:00:00Z"),
  todo("later", new Date(2026, 9, 28, 9), "Dentist"),
  todo("tomorrow", new Date(2026, 9, 26, 9), "Gym"),
  todo("today", new Date(2026, 9, 25, 15), "Call Sam"),
  todo("overdue", new Date(2026, 9, 24, 9), "Renew passport"),
  done("done2", null, "Water plants", "2026-10-25T07:00:00Z"),
];

beforeEach(() => {
  mockCells.length = 0;
  mockScroll.mockClear();
});

it("draws each day's heading over its cards, same-time to-dos together with their clash", async () => {
  const ui = await list([
    todo("call", new Date(2026, 9, 25, 15), "Call Sam"),
    todo("pay", new Date(2026, 9, 25, 15, 5), "Pay rent"),
    todo("gym", new Date(2026, 9, 25, 18), "Gym"),
    todo("milk", null, "Buy milk"),
  ]);
  for (const text of ["todos.group_today", "Call Sam", "Pay rent", "Gym", "todos.group_anytime", "Buy milk", "todos.day_clash_pair"]) {
    expect(ui.getByText(text)).toBeTruthy();
  }
  expect(cells()).toEqual(["# today", "call+pay", "gym", "# anytime", "milk"]);
});

// The page opened on a Today view that hid undated and later to-dos: "Nothing due today" stood
// over two to-dos. It is one list now, every open to-do in its section.
it("lists every section in one list: overdue first, the later days, anytime after them, completed last", async () => {
  await list(EVERY_SECTION);
  expect(cells()).toEqual([
    "# overdue", "overdue",
    "# today", "today",
    "# tomorrow", "tomorrow",
    "# date", "later",
    "# anytime", "anytime",
    "# completed",
  ]);
});

it("names each section as a header, a later day by its date", async () => {
  const ui = await list(EVERY_SECTION);
  const headers = ui.getAllByRole("header").map((node) => node.props.children as string);
  expect(headers.slice(0, 3)).toEqual(["todos.group_overdue", "todos.group_today", "todos.group_tomorrow"]);
  expect(headers[3]).toMatch(/28/);
  expect(headers[4]).toBe("todos.group_anytime");
  // Completed is a button, not a header.
  expect(headers).toHaveLength(5);
});

it("folds Completed under its count, and opens it in place", async () => {
  const onToggleCompleted = jest.fn();
  const ui = await list(EVERY_SECTION, { onToggleCompleted });
  expect(ui.getByText("todos.group_completed_count")).toBeTruthy();
  expect(ui.queryByText("Pay rent")).toBeNull();
  const folded = ui.getByRole("button", { name: "todos.group_completed, 2" });
  expect(folded.props.accessibilityState).toMatchObject({ expanded: false });
  expect(folded.props.accessibilityHint).toBe("todos.completed_expand_hint");
  await fireEvent.press(folded);
  expect(onToggleCompleted).toHaveBeenCalledTimes(1);

  await ui.rerender(element(EVERY_SECTION, { onToggleCompleted, completedOpen: true }));
  expect(cells().slice(-3)).toEqual(["# completed", "done2", "done"]);
  expect(ui.getByText("Pay rent")).toBeTruthy();
  expect(ui.getByText("Water plants")).toBeTruthy();
  const open = ui.getByRole("button", { name: "todos.group_completed, 2" });
  expect(open.props.accessibilityState).toMatchObject({ expanded: true });
  expect(open.props.accessibilityHint).toBe("todos.completed_collapse_hint");
});

it("shows no heading for a section with nothing in it", async () => {
  const ui = await list([todo("anytime", null, "Buy milk")]);
  expect(cells()).toEqual(["# anytime", "anytime"]);
  expect(ui.queryByTestId("todos-completed-heading")).toBeNull();
});

it("offers Show older completed inside the opened Completed section only", async () => {
  const onShowOlder = jest.fn();
  const ui = await list(EVERY_SECTION, { onShowOlder });
  expect(ui.queryByText("todos.show_older_completed")).toBeNull();
  await ui.rerender(element(EVERY_SECTION, { onShowOlder, completedOpen: true }));
  await fireEvent.press(ui.getByText("todos.show_older_completed"));
  expect(onShowOlder).toHaveBeenCalledTimes(1);
});

it("heads Completed with no count when only older completed to-dos are left out", async () => {
  const onShowOlder = jest.fn();
  const ui = await list([todo("anytime", null, "Buy milk")], { onShowOlder });
  expect(cells()).toEqual(["# anytime", "anytime", "# completed"]);
  expect(ui.getByRole("button", { name: "todos.group_completed" })).toBeTruthy();
  await ui.rerender(element([todo("anytime", null, "Buy milk")], { onShowOlder, completedOpen: true }));
  expect(ui.getByText("todos.show_older_completed")).toBeTruthy();
});

describe("revealing a to-do", () => {
  const frames: FrameRequestCallback[] = [];
  beforeEach(() => {
    frames.length = 0;
    jest.spyOn(globalThis, "requestAnimationFrame").mockImplementation((fn) => frames.push(fn));
    jest.spyOn(globalThis, "cancelAnimationFrame").mockImplementation(() => undefined);
  });
  afterEach(() => jest.restoreAllMocks());
  const runFrames = () => act(() => { frames.splice(0).forEach((fn) => fn(0)); });

  it("scrolls its card to the middle of the list once it is drawn, then says so", async () => {
    const onRevealed = jest.fn();
    await list(EVERY_SECTION, { revealId: "anytime", onRevealed });
    await runFrames();
    expect(mockScroll).toHaveBeenCalledWith({ index: 9, animated: true, viewPosition: 0.5 });
    expect(onRevealed).toHaveBeenCalledTimes(1);
  });

  // A done one is under the folded heading: the screen opens Completed, then it is scrolled to.
  it("waits for a done to-do until Completed is open", async () => {
    const onRevealed = jest.fn();
    const ui = await list(EVERY_SECTION, { revealId: "done", onRevealed });
    await runFrames();
    expect(mockScroll).not.toHaveBeenCalled();
    await ui.rerender(element(EVERY_SECTION, { revealId: "done", onRevealed, completedOpen: true }));
    await runFrames();
    expect(mockScroll).toHaveBeenCalledWith({ index: 12, animated: true, viewPosition: 0.5 });
    expect(onRevealed).toHaveBeenCalledTimes(1);
  });

  it("waits for a new to-do's row to arrive", async () => {
    const onRevealed = jest.fn();
    const ui = await list(EVERY_SECTION, { revealId: "new", onRevealed });
    await runFrames();
    expect(mockScroll).not.toHaveBeenCalled();
    const added = [...EVERY_SECTION, todo("new", new Date(2026, 9, 26, 7), "Pack")];
    await ui.rerender(element(added, { revealId: "new", onRevealed }));
    await runFrames();
    expect(mockScroll).toHaveBeenCalledWith({ index: 5, animated: true, viewPosition: 0.5 });
  });
});

// A day was one cell holding every card: 300 to-dos shown mounted 300 rows (jest,
// FlashList's 400x900 layout stand-in), now about 30, the ones on screen.
it("gives FlashList one cell per card, so a long list mounts only the cards on screen", async () => {
  const todos = Array.from({ length: 300 }, (_, i) => todo(`t${i}`, new Date(2026, 9, 25, 9, i * 20)));
  await list(todos);
  const cards = mockCells.at(-1)!.filter((cell) => cell.kind === "card");
  expect(cards).toHaveLength(300);
  expect(cards.every((cell) => cell.todos?.length === 1)).toBe(true);
});

// Each row and heading wrote its date with toLocale*String, an ICU formatter per call:
// 318 for these 300 to-dos (about 40 µs each in Node), and 18 more per re-render.
// lib/datetime/format.ts keeps one formatter per language, zone, clock and style.
it("builds a handful of date formatters for a long list, and none to draw it again", async () => {
  const todos = Array.from({ length: 300 }, (_, i) => todo(`t${i}`, new Date(2026, 9, 20 + (i % 10), 9, i)));
  const dateText = jest.spyOn(Date.prototype, "toLocaleDateString");
  const timeText = jest.spyOn(Date.prototype, "toLocaleTimeString");
  const built = jest.spyOn(Intl, "DateTimeFormat");
  try {
    const builds = () => built.mock.calls.length + dateText.mock.calls.length + timeText.mock.calls.length;
    const ui = await list(todos);
    expect(builds()).toBeLessThanOrEqual(3);
    built.mockClear();
    await ui.rerender(element(todos));
    expect(built).not.toHaveBeenCalled();
    expect(dateText).not.toHaveBeenCalled();
    expect(timeText).not.toHaveBeenCalled();
  } finally {
    jest.restoreAllMocks();
  }
});
