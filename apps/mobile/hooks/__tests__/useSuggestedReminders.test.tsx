import React from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";

jest.mock("expo-router", () => ({
  useFocusEffect: jest.fn(),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => ({ error: jest.fn() }),
}));

const mockSetTodos = jest.fn();
const existingTodo = {
  id: "existing",
  content: "Buy milk",
  checked: false,
  topic: "Groceries",
  due_at: null,
  sort_order: 0,
  chat_id: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

jest.mock("@/contexts/TodosContext", () => ({
  useTodosOptional: () => ({
    todos: [existingTodo],
    setTodos: mockSetTodos,
  }),
}));

jest.mock("@/lib/api", () => ({
  api: {
    addSuggestedReminder: jest.fn(),
    dismissSuggestedReminder: jest.fn(),
    listSuggestedReminders: jest.fn(),
  },
}));

jest.mock("@/lib/cache/suggestedRemindersCache", () => ({
  fetchSuggestedReminders: jest.fn(async () => ({ reminders: [] })),
  getCachedSuggestedReminders: jest.fn(() => ({
    reminders: [
      { id: "sug-1", title: "Package arriving", due_at: "2026-08-24T18:00:00Z" },
    ],
    pending_count: 1,
  })),
  removeSuggestedReminderFromCache: jest.fn(),
  restoreSuggestedReminderToCache: jest.fn(),
}));

jest.mock("@/lib/todos/todoReminders", () => ({
  syncTodoReminders: jest.fn(async () => undefined),
}));

import { useSuggestedReminders } from "@/hooks/useSuggestedReminders";
import { api } from "@/lib/api";
import { syncTodoReminders } from "@/lib/todos/todoReminders";

const mockApi = api as unknown as {
  addSuggestedReminder: jest.Mock;
};

let current: ReturnType<typeof useSuggestedReminders>;

function Probe() {
  current = useSuggestedReminders("tok");
  return <Text>{current.reminders.length}</Text>;
}

describe("useSuggestedReminders", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("schedules local notifications after adding from the composer chip", async () => {
    const created = {
      id: "todo-new",
      content: "Package arriving",
      checked: false,
      topic: "Reminders",
      due_at: "2026-08-24T18:00:00Z",
      sort_order: 0,
      chat_id: null,
      created_at: "2026-08-23T12:00:00Z",
      updated_at: "2026-08-23T12:00:00Z",
    };
    mockApi.addSuggestedReminder.mockResolvedValue(created);

    await act(async () => {
      render(<Probe />);
    });

    let ok: boolean | undefined;
    await act(async () => {
      ok = await current.add("sug-1");
    });

    expect(ok).toBe(true);
    expect(mockSetTodos).toHaveBeenCalled();
    const next = mockSetTodos.mock.calls[0][0] as typeof created[];
    expect(next[0]).toEqual(created);
    expect(next).toEqual(expect.arrayContaining([existingTodo]));
    expect(syncTodoReminders).toHaveBeenCalledWith(next);
  });

  it("removes the suggestion before the API returns", async () => {
    let finish: (created: typeof existingTodo) => void = () => undefined;
    mockApi.addSuggestedReminder.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    await act(async () => {
      render(<Probe />);
    });
    expect(current.reminders).toHaveLength(1);

    let addPromise: Promise<boolean> = Promise.resolve(false);
    await act(async () => {
      addPromise = current.add("sug-1");
      await Promise.resolve();
    });
    expect(current.reminders).toHaveLength(0);

    await act(async () => {
      finish({
        ...existingTodo,
        id: "todo-new",
        content: "Package arriving",
        due_at: "2026-08-24T18:00:00Z",
      });
      await addPromise;
    });
    expect(current.reminders).toHaveLength(0);
  });

  it("restores the suggestion when add fails", async () => {
    mockApi.addSuggestedReminder.mockRejectedValue(new Error("fail"));
    await act(async () => {
      render(<Probe />);
    });

    await act(async () => {
      await current.add("sug-1");
    });

    expect(current.reminders).toHaveLength(1);
    expect(current.reminders[0]?.id).toBe("sug-1");
  });
});
