import type { ReactElement } from "react";
import { StyleSheet } from "react-native";
import { act, render } from "@testing-library/react-native";
import TodosScreen from "@/features/todos/screens/TodosScreen";
import { dateOnly, type TodoDue } from "@/features/todos/model/dueDate";
import type { TodoListRow } from "@/features/todos/model/todoListRows";

let mockSession = 1;
let mockToken: string | null = "token-a";
let mockFocused = true;
let mockRouteParams: Record<string, string> = {};
const mockRefresh = jest.fn(async () => {});
const mockNavigation = { setOptions: jest.fn() };
let mockAdd: { onPress: () => void };
let mockSheet: {
  visible: boolean;
  onClose: () => void;
  onSave: (content: string, due: TodoDue | null, recurrence: null, topic: string) => void;
};
let mockList: {
  onRefresh: () => Promise<void>; refreshing: boolean; rows: TodoListRow[];
  onOpen: (row: { id: string; content: string }) => void; onSelect: (row: { id: string }) => void;
  completedOpen: boolean; onToggleCompleted: () => void; revealId?: string | null; onRevealed?: () => void;
  onShowOlder?: () => void;
};
let mockHeader: { onRetry: () => void; showEmpty: boolean; allDone?: boolean };
let mockOlderCompleted = false;
let mockEditingTodo: { id: string } | null = null;
let mockListMenu: { onSelect: () => void } | undefined;
const mockOpenTodo = jest.fn();
const mockCreate = jest.fn();
const mockInfo = jest.fn();
const mockGetTodos = () => mockTodos;
let mockTodos: {
  id: string;
  content: string;
  checked: boolean;
  due_at: string | null;
  topic: string;
  sort_order: null;
  chat_id: null;
  created_at: string;
  updated_at: string;
}[] = [];
const mockCurrentSession = () => true;
const mockMarkSeenIds = jest.fn(async () => {});
let mockActionParams: { isCurrentView: () => boolean; getTodos: () => unknown; markSeenIds: unknown };

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/AuthContext", () => {
  const React = jest.requireActual("react");
  const Context = React.createContext(0);
  return { TestAuthProvider: Context.Provider, useAuth: () => {
    React.useContext(Context);
    return { token: mockToken, user: { id: "user" } };
  } };
});
jest.mock("expo-router", () => ({
  Redirect: () => null,
  useNavigation: () => mockNavigation,
  useLocalSearchParams: () => mockRouteParams,
  usePreventRemove: () => () => {},
  useFocusEffect: (effect: () => void | (() => void)) => {
    const React = jest.requireActual("react");
    const focused = mockFocused;
    React.useEffect(() => focused ? effect() : undefined, [effect, focused]);
  },
}));
jest.mock("react-native-gesture-handler", () => ({ GestureHandlerRootView: ({ children }: { children: React.ReactNode }) => children }));
jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: { t: (key: string) => key },
  ensureLocale: jest.fn(),
}));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({}) }));
jest.mock("@/ui/feedback/SkeletonLoader", () => ({ SkeletonList: () => null }));
jest.mock("@/ui/controls/AddFab", () => ({ AddFab: (props: typeof mockAdd) => { mockAdd = props; return null; } }));
jest.mock("@/features/todos/components/TodoEditorSheet", () => ({
  TodoEditorSheet: (props: typeof mockSheet & { editTodo?: unknown }) => {
    // The screen renders two instances: the add sheet (no editTodo prop) and
    // the edit sheet (editTodo, possibly null). Tests observe the add sheet.
    if (!("editTodo" in props)) mockSheet = props;
    // The add sheet, drawn beside what it covers: a screen reader must still reach it.
    const { View: MockView } = jest.requireActual("react-native") as typeof import("react-native");
    return !("editTodo" in props) && props.visible ? <MockView testID="todo-add-sheet" accessible /> : null;
  },
}));
jest.mock("@/features/todos/components/TodosScrollList", () => ({ TodosScrollList: (props: typeof mockList & { listHeader: React.ReactNode }) => {
  const { View: MockView } = jest.requireActual("react-native") as typeof import("react-native");
  mockList = props;
  return <MockView testID="todos-list" accessible>{props.listHeader}</MockView>;
} }));
jest.mock("@/features/todos/components/TodosListHeader", () => ({ TodosListHeader: (props: typeof mockHeader) => { mockHeader = props; return null; } }));
jest.mock("@/features/todos/components/TodosListMenu", () => ({ TodosListMenu: (props: typeof mockListMenu) => { mockListMenu = props; return null; } }));
jest.mock("@/features/todos/hooks/useTodosActions", () => ({ useTodosActions: (params: typeof mockActionParams) => {
  mockActionParams = params;
  return {
    busyTodoIds: new Set(),
    editingTodo: mockEditingTodo,
    savingTodo: false,
    handleToggle: jest.fn(),
    openTodoEditor: mockOpenTodo,
    handleDeleteItem: jest.fn(),
    closeTodoEditor: jest.fn(),
    handleCreateTodo: mockCreate,
    handleUpdateTodo: jest.fn(),
  };
} }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => ({ info: mockInfo }) }));
jest.mock("@/features/todos/context/TodosContext", () => ({ useTodos: () => ({ todos: mockTodos, loading: false, error: false,
  getTodos: mockGetTodos, isCurrentSession: mockCurrentSession, markSeenIds: mockMarkSeenIds,
  refresh: mockRefresh, setTodos: jest.fn(), olderCompleted: mockOlderCompleted, showOlderCompleted: jest.fn(),
}) }));

beforeEach(() => {
  jest.clearAllMocks(); mockSession++; mockToken = "token-a"; mockFocused = true;
  mockRouteParams = {}; mockTodos = []; mockOlderCompleted = false; mockEditingTodo = null;
  mockRefresh.mockResolvedValue();
});

it("closes the reminder draft on a context-only account change", async () => {
  const { TestAuthProvider } = jest.requireMock("@/contexts/AuthContext");
  const screen = <TodosScreen />;
  const ui = await render(<TestAuthProvider value={1}>{screen}</TestAuthProvider>);
  await act(() => { mockAdd.onPress(); });
  expect(mockSheet.visible).toBe(true);
  const oldOwner = mockActionParams.isCurrentView;
  mockSession++; mockToken = "token-b";
  await ui.rerender(<TestAuthProvider value={2}>{screen}</TestAuthProvider>);
  expect(mockSheet.visible).toBe(false);
  expect(oldOwner()).toBe(false);
  expect(mockActionParams.isCurrentView()).toBe(true);
});

it("keeps the draft open through a normal access-token refresh", async () => {
  const ui = await render(<TodosScreen />);
  await act(() => { mockAdd.onPress(); });
  mockToken = "refreshed-token";
  await ui.rerender(<TodosScreen />);
  expect(mockSheet.visible).toBe(true);
  expect(mockActionParams.getTodos).toBe(mockGetTodos);
  expect(mockActionParams.markSeenIds).toBe(mockMarkSeenIds);
});

it.each(["account", "blur", "unmount"])("ignores retained Add and Retry callbacks after %s", async (change) => {
  const ui = await render(<TodosScreen />);
  const add = mockAdd.onPress;
  const retry = mockHeader.onRetry;
  if (change === "account") mockSession++;
  if (change === "blur") { mockFocused = false; await ui.rerender(<TodosScreen />); }
  if (change === "unmount") await ui.unmount();
  await act(() => { add(); retry(); });
  expect(mockRefresh).not.toHaveBeenCalled();
});

it("closes a draft when leaving To-do and rejects its old close callback on return", async () => {
  const ui = await render(<TodosScreen />);
  await act(() => { mockAdd.onPress(); });
  const close = mockSheet.onClose;
  mockFocused = false; await ui.rerender(<TodosScreen />);
  mockFocused = true; await ui.rerender(<TodosScreen />);
  expect(mockSheet.visible).toBe(false);
  await act(() => { mockAdd.onPress(); close(); });
  expect(mockSheet.visible).toBe(true);
});

it("deduplicates pull refresh before React rerenders", async () => {
  let resolve!: () => void;
  mockRefresh.mockReturnValue(new Promise<void>((done) => { resolve = done; }));
  await render(<TodosScreen />);
  const refresh = mockList.onRefresh;
  let pending!: Promise<void>;
  await act(() => { pending = refresh(); void refresh(); });
  expect(mockList.refreshing).toBe(true);
  expect(mockRefresh).toHaveBeenCalledTimes(1);
  await act(async () => { resolve(); await pending; });
  expect(mockList.refreshing).toBe(false);
});

it("opens a to-do when its row is tapped", async () => {
  await render(<TodosScreen />);
  const todo = { id: "todo-1", content: "Walk" };
  await act(() => { mockList.onOpen(todo); });
  expect(mockOpenTodo).toHaveBeenCalledWith(todo);
});

it("hands every row the same open and select handlers on each render, so a change redraws only its row", async () => {
  mockTodos = [todoAt("a", 0), todoAt("b", 0)];
  const ui = await render(<TodosScreen />);
  const { onOpen, onSelect } = mockList;
  mockTodos = [{ ...mockTodos[0]!, checked: true }, mockTodos[1]!];
  await ui.rerender(<TodosScreen />);
  expect(mockList.onOpen).toBe(onOpen);
  expect(mockList.onSelect).toBe(onSelect);
});

it("opens a plain to-do draft without any scheduling step", async () => {
  await render(<TodosScreen />);
  await act(async () => { mockAdd.onPress(); });
  expect(mockSheet.visible).toBe(true);
});

function todoAt(id: string, dayOffset: number | null, checked = false) {
  const due = new Date();
  if (dayOffset !== null) due.setDate(due.getDate() + dayOffset);
  due.setHours(15, 0, 0, 0);
  return {
    id,
    content: id,
    checked,
    due_at: dayOffset === null ? null : due.toISOString(),
    topic: "General",
    sort_order: null,
    chat_id: null,
    created_at: "2026-09-01T00:00:00.000Z",
    updated_at: "2026-09-01T00:00:00.000Z",
  };
}

const listed = () => mockList.rows.map((row) => (row.kind === "heading" ? `# ${row.section}` : row.todo.id));

// The page opened on Today, which hid to-dos with no date and later ones: "Nothing due today"
// stood while two to-dos existed. Every to-do is in the one list, each in its section.
it("opens on one list of every to-do, overdue first and completed last, folded", async () => {
  mockTodos = [todoAt("later", 14), todoAt("done", 0, true), todoAt("anytime", null), todoAt("overdue", -1),
    todoAt("today", 0), todoAt("tomorrow", 1)];
  await render(<TodosScreen />);
  expect(listed()).toEqual(["# overdue", "overdue", "# today", "today", "# tomorrow", "tomorrow", "# date", "later",
    "# anytime", "anytime", "# completed", "done"]);
  expect(mockList.completedOpen).toBe(false);
  expect(mockHeader.allDone).toBe(false);

  await act(() => { mockList.onToggleCompleted(); });
  expect(mockList.completedOpen).toBe(true);
  await act(() => { mockList.onToggleCompleted(); });
  expect(mockList.completedOpen).toBe(false);
});

it("opens the reminder a due notification points at, and brings its row on screen for the way back", async () => {
  const due = todoAt("todo-1", 0);
  mockTodos = [todoAt("other", null), due];
  mockRouteParams = { highlight: "todo-1" };
  await render(<TodosScreen />);
  expect(mockOpenTodo).toHaveBeenCalledWith(due);
  expect(mockList.revealId).toBe("todo-1");
  expect(mockList.completedOpen).toBe(false);
  await act(() => { mockList.onRevealed?.(); });
  expect(mockList.revealId).toBeNull();
});

it("opens Completed first when the reminder it points at is done", async () => {
  mockTodos = [todoAt("todo-1", -1, true)];
  mockRouteParams = { highlight: "todo-1" };
  await render(<TodosScreen />);
  expect(mockList.completedOpen).toBe(true);
  expect(mockList.revealId).toBe("todo-1");
});

// A to-do added on Today that Today hid switched the list to another view and said so; in one
// list it is always in its section, and the list scrolls to it.
it.each([
  ["a to-do due in three days", 3, true],
  ["a to-do due today", 0, true],
  ["a date alone in three days", 3, false],
  ["no date at all", null, false],
])("after adding %s, scrolls to it in its section, with no note about a view", async (_name, days, hasTime) => {
  await render(<TodosScreen />);
  await act(() => { mockAdd.onPress(); });
  let due: TodoDue | null = null;
  if (days !== null) {
    const date = new Date();
    date.setDate(date.getDate() + days);
    due = hasTime ? { date, hasTime } : dateOnly(date);
  }
  await act(() => { mockSheet.onSave("Gym", due, null, "General"); });
  const onCreated = mockCreate.mock.calls[0][2] as (created: { id: string; checked: boolean }) => void;
  await act(() => { onCreated({ id: "server-id", checked: false }); });
  expect(mockSheet.visible).toBe(false);
  expect(mockList.revealId).toBe("server-id");
  expect(mockList.completedOpen).toBe(false);
  expect(mockInfo).not.toHaveBeenCalled();
});

it("draws the To-do title alone, with no view under it", async () => {
  await render(<TodosScreen />);
  const options = mockNavigation.setOptions.mock.calls.at(-1)![0] as { headerTitle: () => ReactElement };
  const title = await render(options.headerTitle());
  expect(title.getByText("drawer.reminders")).toBeTruthy();
  expect(title.queryByText(/todos\.menu_/)).toBeNull();
});

it("starts selecting from the ⋯ menu", async () => {
  await render(<TodosScreen />);
  await act(() => { mockListMenu!.onSelect(); });
  const options = mockNavigation.setOptions.mock.calls.at(-1)![0] as { headerRight: () => ReactElement };
  const right = await render(options.headerRight());
  expect(right.getByText("todos.selection_done")).toBeTruthy();
});

it("keeps \"No to-dos yet\" off the page while older completed to-dos are left out", async () => {
  await render(<TodosScreen />);
  expect(mockHeader.showEmpty).toBe(true);
  expect(mockHeader.allDone).toBe(false);
  expect(mockList.onShowOlder).toBeUndefined();
  mockOlderCompleted = true;
  await render(<TodosScreen />);
  // Everything is done: "Nothing left to do" over the Completed heading, which opens onto
  // "Show older completed".
  expect(mockHeader.showEmpty).toBe(false);
  expect(mockHeader.allDone).toBe(true);
  expect(mockList.onShowOlder).toBeDefined();
});

it("says nothing is left to do over the folded Completed heading when every to-do is done", async () => {
  mockTodos = [todoAt("done", 0, true), todoAt("done too", null, true)];
  await render(<TodosScreen />);
  expect(mockHeader.showEmpty).toBe(false);
  expect(mockHeader.allDone).toBe(true);
  expect(listed()).toEqual(["# completed", "done", "done too"]);
  expect(mockList.completedOpen).toBe(false);
});

// The new to-do sheet is drawn in the screen, not a Modal: a screen reader still reached the list
// and the header (back, title, ⋯) under it.
it("hides the header and the list under the new to-do sheet from a screen reader", async () => {
  const header = async () => {
    const options = mockNavigation.setOptions.mock.calls.at(-1)![0] as { headerTitle: () => ReactElement };
    return render(options.headerTitle());
  };
  const ui = await render(<TodosScreen />);
  expect((await header()).getByText("drawer.reminders")).toBeTruthy();
  expect(ui.getByTestId("todos-list")).toBeTruthy();

  expect(ui.queryByTestId("todo-add-sheet")).toBeNull();
  await act(() => { mockAdd.onPress(); });
  expect(ui.queryByTestId("todos-list")).toBeNull();
  expect(ui.getByTestId("todos-list", { includeHiddenElements: true })).toBeTruthy();
  expect(ui.getByTestId("todo-add-sheet")).toBeTruthy();
  const covered = await header();
  expect(covered.queryByText("drawer.reminders")).toBeNull();
  expect(covered.getByText("drawer.reminders", { includeHiddenElements: true })).toBeTruthy();
});

// The new to-do sheet's cover kept the screen's flex with the list gone: the open to-do's
// page got the bottom half, its top half left blank.
it("gives an open to-do's page the whole screen", async () => {
  mockTodos = [todoAt("todo-1", 0)];
  mockEditingTodo = mockTodos[0]!;
  const ui = await render(<TodosScreen />);
  const root = ui.toJSON() as { children: { props: { style?: unknown } }[] };
  const cover = root.children[0]!;
  expect(StyleSheet.flatten(cover.props.style as never)?.flex).toBeUndefined();
});
