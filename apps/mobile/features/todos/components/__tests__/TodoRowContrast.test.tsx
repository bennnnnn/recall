/**
 * An overdue time stays readable on every plane its row is drawn on. A lit row (opened from
 * Home's overdue card or a push, or picked to select) sits on primaryLight, where the danger
 * ink fell under 4.5:1 in every dark accent and light violet (graphite dark 3.59).
 */
import type { ReactNode } from "react";
import { StyleSheet, View } from "react-native";
import { act, render, screen } from "@testing-library/react-native";

import { TodosScrollList } from "@/features/todos/components/TodosScrollList";
import { buildTodoListRows } from "@/features/todos/model/todoListRows";
import { AA, contrastRatio } from "@/lib/__tests__/support/contrast";
import { ACCENT_OPTIONS, DEFAULT_ACCENT } from "@/lib/accent";
import { setAccentSnapshot } from "@/lib/accentRuntime";
import type { Todo } from "@/lib/api";
import { formatDate } from "@/lib/datetime/format";
import { themeFor } from "@/lib/theme";

let mockScheme: "light" | "dark" = "light";
jest.mock("@/lib/colorScheme", () => ({ useResolvedColorScheme: () => mockScheme }));
jest.mock("react-native-gesture-handler/ReanimatedSwipeable", () => {
  const { View: MockView } = jest.requireActual<typeof import("react-native")>("react-native");
  return function MockSwipeable({ children }: { children: ReactNode }) {
    return <MockView>{children}</MockView>;
  };
});
jest.mock("@/lib/haptics", () => ({ selection: jest.fn() }));

/** WCAG 1.4.11: a mark that carries meaning needs 3:1 on its plane. */
const NON_TEXT = 3;
const NOW = new Date(2026, 9, 25, 15);

function todo(id: string, due: Date): Todo {
  return {
    id, content: id, topic: "General", checked: false, due_at: due.toISOString(), recurrence_rule: null,
    sort_order: null, chat_id: null, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
  } as Todo;
}

// A past day's to-do (the Overdue section) and one whose time passed earlier today (pastDue).
const OVERDUE = [todo("yesterday", new Date(2026, 9, 24, 9)), todo("this morning", new Date(2026, 9, 25, 10, 30))];

type State = "unlit" | "highlighted" | "selected" | "highlighted and selected";
const STATES: State[] = ["unlit", "highlighted", "selected", "highlighted and selected"];

function list(item: Todo, state: State) {
  const lit = state !== "unlit";
  const selecting = state === "selected" || state === "highlighted and selected";
  return (
    <TodosScrollList
      rows={buildTodoListRows(OVERDUE, NOW)}
      now={NOW}
      showEmpty={false}
      error={false}
      listHeader={<View />}
      busyTodoIds={new Set()}
      onToggle={jest.fn()}
      onOpen={jest.fn()}
      onDeleteItem={jest.fn()}
      highlight={lit && state !== "selected" ? item.id : undefined}
      selecting={selecting}
      selectedIds={new Set(selecting ? [item.id] : [])}
      onSelect={jest.fn()}
    />
  );
}

type Host = ReturnType<typeof screen.getByText>;

/** The nearest background under a node: the row when it is lit, else the day's card. */
function planeUnder(node: Host): string {
  for (let at = node.parent; at; at = at.parent) {
    const background = StyleSheet.flatten(at.props.style)?.backgroundColor;
    if (typeof background === "string") return background;
  }
  throw new Error("no plane under the node");
}

/** One row's time and its overdue mark, each with the plane it is drawn on. */
async function drawn(item: Todo, state: State) {
  const ui = await render(list(item, state));
  const time = ui.getByText(formatDate(new Date(item.due_at!), "time"));
  const mark = ui.queryAllByTestId("todo-overdue-mark").find((node) => node.parent === time.parent);
  const result = {
    ink: String(StyleSheet.flatten(time.props.style).color),
    plane: planeUnder(time),
    mark: mark ? { ink: String(mark.props.color), plane: planeUnder(mark) } : null,
  };
  await ui.unmount();
  return result;
}

afterEach(async () => {
  mockScheme = "light";
  await act(async () => setAccentSnapshot(DEFAULT_ACCENT));
});

it.each(["light", "dark"] as const)(
  "%s: an overdue time is AA and marked as overdue in every accent and row state",
  async (scheme) => {
    mockScheme = scheme;
    const failures: string[] = [];
    for (const accent of ACCENT_OPTIONS) {
      await act(async () => setAccentSnapshot(accent));
      for (const item of OVERDUE) {
        for (const state of STATES) {
          const { ink, plane, mark } = await drawn(item, state);
          const where = `${accent} ${item.id} ${state}`;
          const ratio = contrastRatio(ink, plane);
          if (ratio < AA) failures.push(`${where}: time ${ratio.toFixed(3)}`);
          if (!mark) failures.push(`${where}: no overdue mark`);
          else if (contrastRatio(mark.ink, mark.plane) < NON_TEXT) {
            failures.push(`${where}: mark ${contrastRatio(mark.ink, mark.plane).toFixed(3)}`);
          }
        }
      }
    }
    expect(failures).toEqual([]);
  },
);

it.each(["light", "dark"] as const)(
  "%s: an unlit overdue time keeps its danger ink on the card; a lit row is primaryLight",
  async (scheme) => {
    mockScheme = scheme;
    for (const accent of ACCENT_OPTIONS) {
      await act(async () => setAccentSnapshot(accent));
      const C = themeFor(scheme, accent);
      const unlit = await drawn(OVERDUE[0]!, "unlit");
      expect({ accent, ink: unlit.ink, plane: unlit.plane }).toEqual({ accent, ink: C.danger, plane: C.surface });
      const lit = await drawn(OVERDUE[0]!, "highlighted");
      expect({ accent, plane: lit.plane, mark: lit.mark?.ink }).toEqual({ accent, plane: C.primaryLight, mark: C.danger });
    }
  },
);
