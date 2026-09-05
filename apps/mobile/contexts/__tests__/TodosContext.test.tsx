import { StrictMode, useEffect } from "react";
import { act, render, waitFor } from "@testing-library/react-native";
import { TodosProvider, useTodos } from "@/contexts/TodosContext";
import { api, type Todo } from "@/lib/api";
import { syncTodoReminders } from "@/lib/todos/todoReminders";
import { loadSeenReminderIds, markReminderIdsSeen, saveSeenReminderIds } from "@/lib/reminderSeen";
import { loadHomeNudgeState, saveHomeNudgeState } from "@/lib/homeReminderNudges";
import { beginTodoMutation, getTodoMutationState } from "@/lib/todos/todoMutationState";

let mockSession = 1;
let mockToken = "token-a";
let mockUserId = "account-a";
let mockLead = 60;
let mockSeen = new Set<string>();
let mockDismissed = new Set<string>();
let mockValue: ReturnType<typeof useTodos>;
const now = new Date("2026-09-04T12:00:00Z").getTime();
const todo: Todo = { id: "t1", content: "Flight", topic: "Reminders", checked: false,
  due_at: new Date(now + 30 * 60_000).toISOString(), created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z", sort_order: null, chat_id: null };
jest.mock("@/contexts/AuthContext", () => ({ useAuthOptional: () => ({ token: mockToken,
  user: { id: mockUserId, reminder_lead_minutes: mockLead, push_notifications_enabled: true } }) }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession, requireTokenSession: jest.fn() }));
jest.mock("@/lib/filePrefs", () => ({}));
jest.mock("@/lib/api", () => ({ api: { listTodos: jest.fn(), updateTodo: jest.fn() } }));
jest.mock("@/lib/todos/todoReminders", () => ({ syncTodoReminders: jest.fn(async () => {}) }));
jest.mock("@/lib/reminderSeen", () => ({
  ...jest.requireActual("@/lib/reminderSeen"),
  loadSeenReminderIds: jest.fn(async () => new Set(mockSeen)),
  saveSeenReminderIds: jest.fn(async (_id: string, ids: Set<string>) => { mockSeen = new Set(ids); }),
  markReminderIdsSeen: jest.fn(async (_id: string, ids: string[]) => { ids.forEach((id) => mockSeen.add(id)); }),
}));
jest.mock("@/lib/homeReminderNudges", () => ({
  ...jest.requireActual("@/lib/homeReminderNudges"),
  loadHomeNudgeState: jest.fn(async () => ({ dismissed: new Set(mockDismissed) })),
  saveHomeNudgeState: jest.fn(async (_id: string, state: { dismissed: Set<string> }) => {
    mockDismissed = new Set(state.dismissed);
  }),
}));

function Probe() { const value = useTodos(); useEffect(() => { mockValue = value; }, [value]); return null; }
function Screen() { return <TodosProvider><Probe /></TodosProvider>; }
function deferred() {
  let resolve!: (rows: Todo[]) => void;
  const promise = new Promise<Todo[]>((done) => { resolve = done; });
  return { promise, resolve };
}
beforeEach(() => {
  jest.clearAllMocks(); mockSession = 1; mockToken = "token-a"; mockUserId = "account-a";
  mockLead = 60; mockSeen = new Set(); mockDismissed = new Set();
  jest.useFakeTimers({ now });
  jest.mocked(api.listTodos).mockResolvedValue([todo]);
  jest.mocked(api.updateTodo).mockResolvedValue(todo);
});
afterEach(() => { jest.restoreAllMocks(); jest.useRealTimers(); });

it("hides the previous account immediately and rejects its late list result", async () => {
  const old = deferred(); const next = deferred();
  jest.mocked(api.listTodos).mockReturnValueOnce(old.promise).mockReturnValueOnce(next.promise);
  const ui = await render(<Screen />);
  await act(() => { mockValue.setTodos([todo]); });
  mockSession++; mockToken = "token-b"; mockUserId = "account-b";
  await ui.rerender(<Screen />);
  expect(mockValue.todos).toEqual([]);
  const b = { ...todo, id: "b" };
  await act(async () => { next.resolve([b]); });
  await act(async () => { old.resolve([todo]); });
  expect(mockValue.todos).toEqual([b]);
});

it("keeps a pending list request and visible rows through normal token refresh", async () => {
  const read = deferred();
  jest.mocked(api.listTodos).mockReturnValue(read.promise);
  const ui = await render(<Screen />);
  mockToken = "refreshed-token";
  await ui.rerender(<Screen />);
  expect(api.listTodos).toHaveBeenCalledTimes(1);
  await act(async () => { read.resolve([todo]); });
  expect(mockValue.todos).toEqual([todo]);
});

it("replays a mutation over a pending read while retaining other server rows", async () => {
  await render(<Screen />);
  await waitFor(() => expect(mockValue.todos).toEqual([todo]));
  const read = deferred();
  jest.mocked(api.listTodos).mockReturnValueOnce(read.promise);
  let refresh!: Promise<void>;
  await act(() => { refresh = mockValue.refresh({ force: true }); });
  await act(() => { mockValue.setTodos((rows) => rows.filter((row) => row.id !== todo.id)); });
  const unseen = { ...todo, id: "new" };
  await act(async () => { read.resolve([todo, unseen]); await refresh; });
  expect(mockValue.todos).toEqual([unseen]);
});

it("does not let a retained setter write to another account", async () => {
  const ui = await render(<Screen />);
  const setOld = mockValue.setTodos;
  mockSession++; mockToken = "token-b"; mockUserId = "account-b";
  jest.mocked(api.listTodos).mockResolvedValue([]);
  await ui.rerender(<Screen />);
  await act(() => { setOld([todo]); });
  expect(mockValue.todos).toEqual([]);
});

it("synchronizes device reminders after an accepted local list mutation", async () => {
  await render(<Screen />);
  await waitFor(() => expect(mockValue.todos).toEqual([todo]));
  jest.mocked(syncTodoReminders).mockClear();
  await act(() => { mockValue.setTodos([]); });
  await waitFor(() => expect(jest.mocked(syncTodoReminders).mock.calls.at(-1)?.[0]).toEqual([]));
});

it("marks the same configured lead window seen that contributes to the badge", async () => {
  await render(<Screen />);
  await waitFor(() => expect(mockValue.todos).toEqual([todo]));
  await act(async () => { await mockValue.markSeen(); });
  const writes = [...jest.mocked(saveSeenReminderIds).mock.calls, ...jest.mocked(markReminderIdsSeen).mock.calls];
  expect(writes.some(([, ids]) => [...ids].includes(todo.id))).toBe(true);
});

it("preserves canonical server recurrence dates without a client PATCH", async () => {
  const recurring = { ...todo, recurrence_rule: "daily" as const, due_at: "2020-01-01T12:00:00Z" };
  jest.mocked(api.listTodos).mockResolvedValue([recurring]);
  await render(<Screen />);
  await waitFor(() => expect(mockValue.loading).toBe(false));
  expect(api.updateTodo).not.toHaveBeenCalled();
  expect(mockValue.todos).toEqual([recurring]);
});

it("retains valid rows on a failed refresh and allows retry", async () => {
  await render(<Screen />);
  await waitFor(() => expect(mockValue.todos).toEqual([todo]));
  jest.mocked(api.listTodos).mockRejectedValueOnce(new Error("offline"));
  await act(async () => { await mockValue.refresh({ force: true }); });
  expect(mockValue.todos).toEqual([todo]);
  expect(mockValue.error).toBe(true);
  await act(async () => { await mockValue.refresh({ force: true }); });
  expect(mockValue.error).toBe(false);
});

it("waits for a pending mutation before beginning a newer list read", async () => {
  await render(<Screen />);
  const mutations = getTodoMutationState(`${mockSession}:${mockUserId}`);
  const release = beginTodoMutation(mutations, todo.id)!;
  try {
    await act(() => { mockValue.setTodos([]); });
    let refresh!: Promise<void>;
    await act(() => { refresh = mockValue.refresh({ force: true }); });
    expect(api.listTodos).toHaveBeenCalledTimes(1);
    expect(mockValue.todos).toEqual([]);
    jest.mocked(api.listTodos).mockResolvedValueOnce([]);
    await act(async () => { release(); await refresh; });
    expect(api.listTodos).toHaveBeenCalledTimes(2);
    expect(mockValue.todos).toEqual([]);
  } finally { release(); }
});

it("preserves seen and dismissed state if an optimistic deletion rolls back", async () => {
  mockSeen.add(todo.id);
  jest.mocked(loadHomeNudgeState).mockResolvedValueOnce({ dismissed: new Set([todo.id]) });
  await render(<Screen />);
  await waitFor(() => expect(mockValue.homeNudgeDismissed.has(todo.id)).toBe(true));
  await act(() => { mockValue.setTodos([]); });
  await act(() => { mockValue.setTodos([todo]); });
  expect(mockValue.seenReminderIds.has(todo.id)).toBe(true);
  expect(mockValue.homeNudgeDismissed.has(todo.id)).toBe(true);
});

it.each(["seen", "dismissed"] as const)("retries a failed %s write on the next synchronization", async (failed) => {
  jest.spyOn(console, "warn").mockImplementation(() => {});
  const ui = await render(<Screen />);
  await waitFor(() => expect(mockValue.todos).toEqual([todo]));
  if (failed === "seen") jest.mocked(saveSeenReminderIds).mockRejectedValueOnce(new Error("storage"));
  else jest.mocked(saveHomeNudgeState).mockRejectedValueOnce(new Error("storage"));
  await act(async () => { await mockValue.dismissReminderNudge(todo.id); });
  expect(mockValue.homeNudgeDismissed.has(todo.id)).toBe(true);
  expect(mockValue.seenReminderIds.has(todo.id)).toBe(true);
  expect((failed === "seen" ? mockSeen : mockDismissed).has(todo.id)).toBe(false);

  // A list synchronization must retry storage even though the in-memory IDs agree.
  await act(() => { mockValue.setTodos((rows) => [...rows]); });
  await waitFor(() => {
    expect(mockSeen.has(todo.id)).toBe(true);
    expect(mockDismissed.has(todo.id)).toBe(true);
  });
  expect(saveSeenReminderIds).toHaveBeenCalledTimes(failed === "seen" ? 2 : 1);
  expect(saveHomeNudgeState).toHaveBeenCalledTimes(failed === "dismissed" ? 2 : 1);
  await ui.unmount();
  await render(<Screen />);
  await waitFor(() => expect(mockValue.homeNudgeDismissed.has(todo.id)).toBe(true));
  expect(mockValue.seenReminderIds.has(todo.id)).toBe(true);
});

it("releases a mutation wait immediately when its account owner changes", async () => {
  const ui = await render(<Screen />);
  const mutations = getTodoMutationState(`${mockSession}:${mockUserId}`);
  const release = beginTodoMutation(mutations, todo.id)!;
  try {
    let waiting!: Promise<void>;
    await act(() => { waiting = mockValue.refresh({ force: true }); });
    expect(mutations.listeners.size).toBe(1);
    mockSession++; mockToken = "token-b"; mockUserId = "account-b";
    jest.mocked(api.listTodos).mockResolvedValue([]);
    await ui.rerender(<Screen />);
    await act(async () => { await waiting; });
    expect(mutations.listeners.size).toBe(0);
    expect(mockValue.todos).toEqual([]);
    expect(api.listTodos).toHaveBeenCalledTimes(2);
  } finally { release(); }
});

it("keeps a newer account's mutation registry when an old afterPending wait resumes", async () => {
  const old = deferred();
  jest.mocked(api.listTodos).mockReturnValueOnce(old.promise);
  const ui = await render(<Screen />);
  let waiting!: Promise<void>;
  await act(() => { waiting = mockValue.refresh({ afterPending: true }); });
  mockSession++; mockToken = "token-b"; mockUserId = "account-b";
  jest.mocked(api.listTodos).mockResolvedValue([]);
  await ui.rerender(<Screen />);
  const key = `${mockSession}:${mockUserId}`;
  const mutations = getTodoMutationState(key);
  const release = beginTodoMutation(mutations, "b")!;
  try {
    await act(async () => { old.resolve([todo]); await waiting; });
    expect(getTodoMutationState(key)).toBe(mutations);
    expect(getTodoMutationState(key).pendingIds.has("b")).toBe(true);
  } finally { release(); }
});

it("starts a fresh recovery read after an older response replays a rollback", async () => {
  await render(<Screen />);
  const old = deferred();
  jest.mocked(api.listTodos).mockReturnValueOnce(old.promise).mockResolvedValueOnce([]);
  let first!: Promise<void>; let recovery!: Promise<void>;
  await act(() => { first = mockValue.refresh({ force: true }); });
  await act(() => { mockValue.setTodos([]); mockValue.setTodos([todo]);
    recovery = mockValue.refresh({ force: true, afterPending: true }); });
  await act(async () => { old.resolve([]); await first; await recovery; });
  expect(api.listTodos).toHaveBeenCalledTimes(3);
  expect(mockValue.todos).toEqual([]);
});

it("replaces an aborted request controller during StrictMode effect replay", async () => {
  await render(<StrictMode><Screen /></StrictMode>);
  await waitFor(() => expect(mockValue.todos).toEqual([todo]));
  const signals = jest.mocked(api.listTodos).mock.calls.map(([, options]) => options?.signal);
  expect(signals.some((signal) => signal?.aborted)).toBe(true);
  expect(signals.at(-1)?.aborted).toBe(false);
});

it("rejects stale badge hydration without losing a newer account's seen state", async () => {
  let finish!: (ids: Set<string>) => void;
  jest.mocked(loadSeenReminderIds).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const ui = await render(<Screen />);
  mockSession++; mockToken = "token-b"; mockUserId = "account-b";
  const b = { ...todo, id: "b" };
  jest.mocked(api.listTodos).mockResolvedValue([b]);
  mockSeen = new Set([b.id]);
  await ui.rerender(<Screen />);
  await act(async () => { finish(new Set([todo.id])); });
  expect([...mockValue.seenReminderIds]).toEqual([b.id]);
});
