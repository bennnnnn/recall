import React from "react";
import { Alert } from "react-native";
import { act, render } from "@testing-library/react-native";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useTodosCalendarIntegration } from "@/hooks/useTodosCalendarIntegration";
import { api, type GoogleCalendarEvent, type SuggestedReminder, type Todo } from "@/lib/api";
import { fetchSuggestedReminders } from "@/lib/cache/suggestedRemindersCache";
import { syncTodoReminders } from "@/lib/todos/todoReminders";

let mockSession = 0;
let mockSuggestions: SuggestedReminder[] = [];
const mockListeners = new Set<() => void>();
let mockBlur: (() => void) | undefined;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: "token" }) }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
jest.mock("expo-router", () => ({ useFocusEffect: (callback: () => (() => void) | undefined) => {
  const react = jest.requireActual<typeof React>("react");
  react.useEffect(() => { mockBlur = callback(); return mockBlur; }, [callback]);
} }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/lib/todos/todoReminders", () => ({ syncTodoReminders: jest.fn() }));
jest.mock("@/lib/api", () => ({ api: {
  listGoogleCalendarEvents: jest.fn(), addSuggestedReminder: jest.fn(), dismissSuggestedReminder: jest.fn(),
} }));
jest.mock("@/lib/cache/suggestedRemindersCache", () => ({
  fetchSuggestedReminders: jest.fn(),
  getCachedSuggestedReminders: () => ({ reminders: mockSuggestions, pending_count: mockSuggestions.length }),
  subscribeSuggestedRemindersCache: (listener: () => void) => {
    mockListeners.add(listener); return () => { mockListeners.delete(listener); };
  },
  removeSuggestedReminderFromCache: (id: string, session = mockSession) => {
    if (session !== mockSession) return;
    mockSuggestions = mockSuggestions.filter((item) => item.id !== id);
    mockListeners.forEach((listener) => listener());
  },
  restoreSuggestedReminderToCache: (reminder: SuggestedReminder, session = mockSession) => {
    if (session !== mockSession) return;
    if (!mockSuggestions.some((item) => item.id === reminder.id)) mockSuggestions = [...mockSuggestions, reminder];
    mockListeners.forEach((listener) => listener());
  },
  dropSuggestedReminder: (id: string, set: (update: (rows: SuggestedReminder[]) => SuggestedReminder[]) => void) => {
    mockSuggestions = mockSuggestions.filter((item) => item.id !== id);
    set((rows) => rows.filter((item) => item.id !== id));
  },
  undeleteSuggestedReminder: (reminder: SuggestedReminder, set: (update: (rows: SuggestedReminder[]) => SuggestedReminder[]) => void) => {
    mockSuggestions = [...mockSuggestions, reminder];
    set((rows) => [...rows, reminder]);
  },
}));
const mockApi = jest.mocked(api);
const mockFetch = jest.mocked(fetchSuggestedReminders);
const event: GoogleCalendarEvent = { id: "event", title: "Meeting", start_at: "2026-09-04T18:00:00Z", all_day: false };
const suggestion: SuggestedReminder = { id: "suggestion", title: "Reply", due_at: event.start_at,
  notes: null, confidence: 1, source_snippet: null, source_sender: null, status: "pending",
  created_at: event.start_at, gmail_message_id: "email" };
const todo: Todo = { id: "todo", content: "Reply", topic: "General", checked: false,
  due_at: event.start_at, sort_order: null, chat_id: null, created_at: event.start_at, updated_at: event.start_at };
let rows: Todo[];
let viewCurrent = true;
const refresh = jest.fn(async (_opts?: { silent?: boolean; force?: boolean; afterPending?: boolean }) => undefined);
const markSeen = jest.fn(async () => undefined);
const setTodos = jest.fn((update: React.SetStateAction<Todo[]>) => { rows = typeof update === "function" ? update(rows) : update; });
let current: ReturnType<typeof useTodosCalendarIntegration>;
function Probe({ token = "token", highlight, viewGuard }: { token?: string; highlight?: string; viewGuard?: () => boolean }) {
  const result = useTodosCalendarIntegration({ token, todos: rows, highlight, refresh, markSeen, setTodos,
    isCurrentView: viewGuard ?? (() => viewCurrent) });
  React.useLayoutEffect(() => { current = result; });
  return null;
}
function deferred<T>() {
  let resolve!: (value: T) => void; let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
beforeEach(() => {
  jest.clearAllMocks();
  mockSession++;
  rows = [todo];
  viewCurrent = true;
  mockSuggestions = [suggestion];
  mockApi.listGoogleCalendarEvents.mockResolvedValue({ events: [event] });
  mockFetch.mockImplementation(async () => ({ reminders: mockSuggestions, pending_count: mockSuggestions.length }));
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
});

it.each(["throw", "load_error"])("keeps calendar rows when a refreshed read fails with %s", async (failure) => {
  await render(<Probe />);
  if (failure === "throw") mockApi.listGoogleCalendarEvents.mockRejectedValueOnce(new Error("offline"));
  else mockApi.listGoogleCalendarEvents.mockResolvedValueOnce({ events: [], load_error: "offline" });
  await act(async () => { await current.loadCalendarEvents(); });
  expect(current.calendarEvents).toEqual([event]);
  expect(current.calendarLoadError).toBe(true);
});

it("keeps cached suggestions and surfaces a null failed read", async () => {
  await render(<Probe />);
  mockFetch.mockResolvedValueOnce(null);
  await act(async () => { await current.loadSuggestedReminders(); });
  expect(current.suggestedReminders).toEqual([suggestion]);
  expect(current.suggestedLoadError).toBe(true);
});

it("awaits the focus refresh before marking reminders seen", async () => {
  const pending = deferred<void>();
  refresh.mockReturnValueOnce(pending.promise);
  await render(<Probe />);
  expect(markSeen).not.toHaveBeenCalled();
  await act(async () => { pending.resolve(); });
  expect(markSeen).toHaveBeenCalledTimes(1);
});

it("does not snap a manually selected day back when a highlighted todo updates", async () => {
  const view = await render(<Probe highlight={todo.id} />);
  await act(async () => { current.goToDay("2026-09-12"); });
  rows = [{ ...todo, checked: true }];
  await view.rerender(<Probe highlight={todo.id} />);
  expect(current.selectedDay).toBe("2026-09-12");
});

it("rejects retained callbacks immediately when an account session changes", async () => {
  await render(<Probe />);
  const old = current;
  mockSession++;
  await act(async () => {
    await old.loadCalendarEvents();
    await old.loadSuggestedReminders();
    await old.handleAddSuggestion(suggestion);
    await old.handleDismissSuggestion(suggestion);
  });
  expect(mockApi.listGoogleCalendarEvents).toHaveBeenCalledTimes(1);
  expect(mockFetch).toHaveBeenCalledTimes(1);
  expect(mockApi.addSuggestedReminder).not.toHaveBeenCalled();
  expect(mockApi.dismissSuggestedReminder).not.toHaveBeenCalled();
});

it("ignores a calendar response after blur and does not mark its refresh seen", async () => {
  const read = deferred<{ events: GoogleCalendarEvent[] }>();
  const refreshed = deferred<void>();
  mockApi.listGoogleCalendarEvents.mockReturnValueOnce(read.promise);
  refresh.mockReturnValueOnce(refreshed.promise);
  await render(<Probe />);
  viewCurrent = false;
  await act(async () => { mockBlur?.(); read.resolve({ events: [event] }); refreshed.resolve(); });
  expect(current.calendarEvents).toEqual([]);
  expect(markSeen).not.toHaveBeenCalled();
});

it("keeps an add locked across visits and deduplicates its created todo", async () => {
  const adding = deferred<Todo>();
  mockApi.addSuggestedReminder.mockReturnValue(adding.promise);
  const first = await render(<Probe />);
  let pending!: Promise<void>;
  await act(async () => { pending = current.handleAddSuggestion(suggestion); });
  await first.unmount();
  await render(<Probe />);
  expect(current.suggestionBusyId).toBe(suggestion.id);
  await act(async () => { await current.handleAddSuggestion(suggestion); });
  expect(mockApi.addSuggestedReminder).toHaveBeenCalledTimes(1);
  await act(async () => { adding.resolve(todo); await pending; });
  expect(rows).toEqual([todo]);
  expect(current.suggestionBusyId).toBeNull();
  expect(refresh).toHaveBeenCalledWith({ silent: true, force: true, afterPending: true });
  expect(syncTodoReminders).not.toHaveBeenCalled();
});

it("reconciles a failed suggestion mutation after its original visit unmounts", async () => {
  const dismissal = deferred<void>();
  mockApi.dismissSuggestedReminder.mockReturnValue(dismissal.promise);
  const first = await render(<Probe />);
  let pending!: Promise<void>;
  await act(async () => { pending = current.handleDismissSuggestion(suggestion); });
  await first.unmount();
  await render(<Probe />);
  mockFetch.mockImplementationOnce(async () => {
    mockSuggestions = [];
    mockListeners.forEach((listener) => listener());
    return { reminders: [], pending_count: 0 };
  });
  await act(async () => { dismissal.reject(new Error("connection lost")); await pending; });
  expect(mockFetch).toHaveBeenLastCalledWith("token", { force: true, afterPending: true });
  expect(current.suggestedReminders).toEqual([]);
  expect(Alert.alert).not.toHaveBeenCalled();
});

function OwnedProbe() {
  const owner = useAccountViewOwner();
  return <Probe key={owner.key} viewGuard={owner.isCurrent} />;
}

it("loads once when the actual account-view wrapper becomes focused", async () => {
  await render(<OwnedProbe />);
  expect(mockApi.listGoogleCalendarEvents).toHaveBeenCalledTimes(1);
  expect(mockFetch).toHaveBeenCalledTimes(1);
  expect(refresh).toHaveBeenCalledTimes(1);
  expect(markSeen).toHaveBeenCalledTimes(1);
  expect(current.calendarEvents).toEqual([event]);
});
