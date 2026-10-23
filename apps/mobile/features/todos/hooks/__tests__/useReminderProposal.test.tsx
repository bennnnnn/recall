import { act, renderHook } from "@testing-library/react-native";

import { applySavedRows, useReminderProposal } from "@/features/todos/hooks/useReminderProposal";
import { api, type Todo } from "@/lib/api";
import { notifyDestructive, notifyError, notifySuccess, tap } from "@/lib/haptics";

jest.mock("@/lib/api", () => ({ api: { confirmReminderProposal: jest.fn() } }));
jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
  notifySuccess: jest.fn(),
  notifyError: jest.fn(),
  notifyDestructive: jest.fn(),
}));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: "tok" }) }));
const mockTodos = { setTodos: jest.fn(), refresh: jest.fn(async () => undefined) };
jest.mock("@/features/todos/context/TodosContext", () => ({ useTodosOptional: () => mockTodos }));
jest.mock("@/features/todos/model/reminderProposal", () => ({
  ...jest.requireActual("@/features/todos/model/reminderProposal"),
  isProposalSaved: () => false,
  markProposalSaved: jest.fn(),
}));

const row = (id: string, content = id): Todo => ({
  id,
  content,
  topic: "General",
  checked: false,
  due_at: null,
  sort_order: null,
  chat_id: null,
  created_at: "2026-01-01T00:00:00.000Z",
  updated_at: "2026-01-01T00:00:00.000Z",
});
const proposal = {
  proposalId: "p1",
  items: [{ action: "add", title: "Call mom" }],
} as Parameters<typeof useReminderProposal>[0];

beforeEach(() => jest.clearAllMocks());

it("puts saved rows in place, adds new ones first and drops deleted ones", () => {
  const rows = [row("a"), row("b"), row("c")];
  expect(applySavedRows(rows, [row("b", "B moved"), row("new")], ["c"]).map((r) => r.content))
    .toEqual(["new", "a", "B moved"]);
});

it("applies the rows a tap saved instead of reading the list again (NET-16)", async () => {
  jest.mocked(api.confirmReminderProposal).mockResolvedValue({ items: [], todos: [row("new")], deleted_ids: [] });
  const { result } = await renderHook(() => useReminderProposal(proposal));
  await act(async () => { await result.current.confirm(); });
  expect(mockTodos.setTodos).toHaveBeenCalledTimes(1);
  const update = mockTodos.setTodos.mock.calls[0][0] as (rows: Todo[]) => Todo[];
  expect(update([row("a")]).map((r) => r.id)).toEqual(["new", "a"]);
  expect(mockTodos.refresh).not.toHaveBeenCalled();
});

it("reads the list when another device saved the card first", async () => {
  jest.mocked(api.confirmReminderProposal).mockResolvedValue({ items: [], todos: null, deleted_ids: [] });
  const { result } = await renderHook(() => useReminderProposal(proposal));
  await act(async () => { await result.current.confirm(); });
  expect(mockTodos.refresh).toHaveBeenCalledWith({ silent: true, force: true });
  expect(mockTodos.setTodos).not.toHaveBeenCalled();
});

const haptics = [tap, notifySuccess, notifyError, notifyDestructive];
const hapticCount = () => haptics.reduce((sum, fn) => sum + jest.mocked(fn).mock.calls.length, 0);

it.each([
  ["a saved reminder", "add", notifySuccess],
  ["a confirmed delete", "delete", notifyDestructive],
] as const)("confirms %s with one haptic once it is saved", async (_name, action, played) => {
  jest.mocked(api.confirmReminderProposal).mockResolvedValue({ items: [], todos: [], deleted_ids: [] });
  const card = { ...proposal, items: [{ action, title: "Call mom" }] } as typeof proposal;
  const { result } = await renderHook(() => useReminderProposal(card));
  await act(async () => { await result.current.confirm(); });
  expect(played).toHaveBeenCalledTimes(1);
  expect(hapticCount()).toBe(1);
  // A second tap on a saved card does nothing.
  await act(async () => { await result.current.confirm(); });
  expect(hapticCount()).toBe(1);
});

it("says a failed save with a haptic and no success", async () => {
  jest.mocked(api.confirmReminderProposal).mockRejectedValue(Object.assign(new Error("gone"), { status: 410 }));
  const { result } = await renderHook(() => useReminderProposal(proposal));
  await act(async () => { await result.current.confirm(); });
  expect(result.current.error).toBe("expired");
  expect(notifyError).toHaveBeenCalledTimes(1);
  expect(notifySuccess).not.toHaveBeenCalled();
});
