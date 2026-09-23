import { act, render } from "@testing-library/react-native";
import TodosScreen from "@/features/todos/screens/TodosScreen";

let mockSession = 1;
let mockToken: string | null = "token-a";
let mockFocused = true;
let mockRouteParams: Record<string, string> = {};
let mockSuggestedReminders: { id: string; title: string }[] = [];
const mockRefresh = jest.fn(async () => {});
const mockT = (key: string) => key;
const mockNavigation = { setOptions: jest.fn() };
let mockAdd: { onPress: () => void };
let mockSheet: { visible: boolean; onClose: () => void };
let mockList: { onRefresh: () => Promise<void>; refreshing: boolean; rows: unknown[] };
let mockHeader: { onRetry: () => void; calendarNudge?: { title: string; startAt: string } };
const mockGetTodos = () => [];
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
  useFocusEffect: (effect: () => void | (() => void)) => {
    const React = jest.requireActual("react");
    const focused = mockFocused;
    React.useEffect(() => focused ? effect() : undefined, [effect, focused]);
  },
}));
jest.mock("react-native-gesture-handler", () => ({ GestureHandlerRootView: ({ children }: { children: React.ReactNode }) => children }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: mockT }) }));
jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: { t: (key: string) => key },
  ensureLocale: jest.fn(),
}));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({}) }));
jest.mock("@/components/SkeletonLoader", () => ({ SkeletonList: () => null }));
jest.mock("@/components/AddFab", () => ({ AddFab: (props: typeof mockAdd) => { mockAdd = props; return null; } }));
jest.mock("@/features/todos/components/TodoEditorSheet", () => ({
  TodoEditorSheet: (props: typeof mockSheet & { editTodo?: unknown }) => {
    // The screen renders two instances: the add sheet (no editTodo prop) and
    // the edit sheet (editTodo, possibly null). Tests observe the add sheet.
    if (!("editTodo" in props)) mockSheet = props;
    return null;
  },
}));
jest.mock("@/features/todos/components/TodosScrollList", () => ({ TodosScrollList: (props: typeof mockList & { listHeader: React.ReactNode }) => { mockList = props; return props.listHeader; } }));
jest.mock("@/features/todos/components/TodosListHeader", () => ({ TodosListHeader: (props: typeof mockHeader) => { mockHeader = props; return null; } }));
jest.mock("@/features/todos/hooks/useTodosActions", () => ({ useTodosActions: (params: typeof mockActionParams) => {
  mockActionParams = params;
  return {
    busyTodoIds: new Set(),
    editingTodo: null,
    savingTodo: false,
    handleToggle: jest.fn(),
    openTodoEditor: jest.fn(),
    handleDeleteItem: jest.fn(),
    closeTodoEditor: jest.fn(),
    handleCreateTodo: jest.fn(),
    handleUpdateTodo: jest.fn(),
  };
} }));
jest.mock("@/features/todos/hooks/useSuggestedReminders", () => ({ useSuggestedReminders: () => ({
  reminders: mockSuggestedReminders,
  busyIds: new Set(),
  refresh: jest.fn(async () => {}),
  add: jest.fn(),
  dismiss: jest.fn(),
}) }));
jest.mock("@/features/todos/context/TodosContext", () => ({ useTodos: () => ({ todos: [], loading: false, error: false,
  getTodos: mockGetTodos, isCurrentSession: mockCurrentSession, markSeenIds: mockMarkSeenIds,
  refresh: mockRefresh, setTodos: jest.fn(),
}) }));

beforeEach(() => {
  jest.clearAllMocks(); mockSession++; mockToken = "token-a"; mockFocused = true;
  mockRouteParams = {}; mockSuggestedReminders = [];
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

it("opens a plain to-do draft without any scheduling step", async () => {
  await render(<TodosScreen />);
  await act(async () => { mockAdd.onPress(); });
  expect(mockSheet.visible).toBe(true);
});

it("shows the exact calendar event carried by a notification", async () => {
  mockRouteParams = {
    eventTitle: "Design review",
    eventStart: "2026-09-18T17:30:00.000Z",
  };
  await render(<TodosScreen />);
  expect(mockHeader.calendarNudge).toEqual({
    title: "Design review",
    startAt: "2026-09-18T17:30:00.000Z",
  });
});

it("includes pending email suggestions in the actionable To-do list", async () => {
  mockSuggestedReminders = [{ id: "suggestion-1", title: "Reply to recruiter" }];
  await render(<TodosScreen />);
  expect(mockList.rows.slice(0, 2)).toMatchObject([
    { kind: "heading", section: "suggested", count: 1 },
    { kind: "suggestion", reminder: { id: "suggestion-1" } },
  ]);
});
