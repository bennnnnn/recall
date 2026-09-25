import React from "react";
import { Alert, Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useTodosActions } from "@/features/todos/hooks/useTodosActions";
import { api, type Todo } from "@/lib/api";

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 0 }));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: { t: (key: string) => key },
  ensureLocale: jest.fn(),
}));

jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));

jest.mock("@/features/todos/model/todoReminders", () => ({
  cancelTodoReminder: jest.fn(async () => undefined),
  syncTodoReminders: jest.fn(),
}));

jest.mock("@/features/todos/model/reminderSeen", () => ({
  markReminderIdsSeen: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  api: {
    createTodo: jest.fn(),
    updateTodo: jest.fn(),
    deleteTodo: jest.fn(),
  },
}));


function todo(partial: Partial<Todo> & Pick<Todo, "id" | "content">): Todo {
  return {
    topic: "General",
    checked: false,
    due_at: null,
    sort_order: null,
    chat_id: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    ...partial,
  };
}

const setTodos = jest.fn();
const refresh = jest.fn(async () => undefined);

let actions: ReturnType<typeof useTodosActions>;

function Probe({ todos }: { todos: Todo[] }) {
  const result = useTodosActions({
    token: "tok",
    userId: "user-1",
    todos,
    setTodos,
    refresh,
  });
  React.useLayoutEffect(() => {
    actions = result;
  }, [result]);
  return <Text>todos actions</Text>;
}

describe("useTodosActions reminders", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Alert, "alert").mockImplementation(() => {});
  });

  it("creates optimistically and closes the sheet only after the API succeeds", async () => {
    let finish: (created: Todo) => void = () => undefined;
    (api.createTodo as jest.Mock).mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    const onCreated = jest.fn();
    const due = new Date("2026-08-24T18:00:00.000Z");
    await act(async () => {
      render(<Probe todos={[]} />);
    });

    let createPromise: Promise<void> = Promise.resolve();
    await act(async () => {
      createPromise = actions.handleCreateTodo("Call mom", due, onCreated);
      await Promise.resolve();
    });

    expect(onCreated).not.toHaveBeenCalled();
    expect(setTodos).toHaveBeenCalled();
    const addUpdater = setTodos.mock.calls[0][0] as (prev: Todo[]) => Todo[];
    const added = addUpdater([]);
    expect(added[0]).toMatchObject({
      content: "Call mom",
      due_at: due.toISOString(),
    });
    expect(added[0].id).toMatch(/^local-todo-\d+-\d+$/);
    expect(api.createTodo).toHaveBeenCalled();

    const created = todo({
      id: "server-1",
      content: "Call mom",
      due_at: due.toISOString(),
    });
    await act(async () => {
      finish(created);
      await createPromise;
    });
    expect(onCreated).toHaveBeenCalledTimes(1);
    const swapUpdater = setTodos.mock.calls.at(-1)?.[0] as (prev: Todo[]) => Todo[];
    expect(swapUpdater(added)[0]).toEqual(created);
  });

  it("rolls back an optimistic reminder when create fails", async () => {
    (api.createTodo as jest.Mock).mockRejectedValue(new Error("fail"));
    const onCreated = jest.fn();
    await act(async () => {
      render(<Probe todos={[]} />);
    });

    await act(async () => {
      await actions.handleCreateTodo(
        "Call mom",
        new Date("2026-08-24T18:00:00.000Z"),
        onCreated,
      );
    });

    const addUpdater = setTodos.mock.calls[0][0] as (prev: Todo[]) => Todo[];
    const added = addUpdater([]);
    const rollback = setTodos.mock.calls.at(-1)?.[0] as (prev: Todo[]) => Todo[];
    expect(rollback(added)).toEqual([]);
    expect(onCreated).not.toHaveBeenCalled();
    expect(Alert.alert).toHaveBeenCalled();
  });

  it("creates a plain to-do without a due date", async () => {
    const created = todo({ id: "plain-1", content: "Buy milk" });
    (api.createTodo as jest.Mock).mockResolvedValue(created);
    await act(async () => {
      render(<Probe todos={[]} />);
    });

    await act(async () => {
      await actions.handleCreateTodo("Buy milk", null, jest.fn());
    });

    expect(api.createTodo).toHaveBeenCalledWith("tok", "Buy milk", "General", {
      dueAt: null,
      recurrenceRule: null,
    });
    const addUpdater = setTodos.mock.calls[0][0] as (prev: Todo[]) => Todo[];
    expect(addUpdater([])[0]).toMatchObject({ content: "Buy milk", due_at: null });
  });

  it("moves a due date immediately and rolls back on failure", async () => {
    (api.updateTodo as jest.Mock).mockRejectedValue(new Error("fail"));
    const existing = todo({
      id: "r1",
      content: "Package",
      due_at: "2026-08-23T18:00:00.000Z",
    });
    await act(async () => {
      render(<Probe todos={[existing]} />);
    });

    await act(async () => {
      actions.openTodoEditor(existing);
    });
    expect(actions.editingTodo?.id).toBe("r1");
    await act(async () => {
      await actions.handleUpdateTodo(
        existing,
        "Package",
        new Date("2026-08-25T18:00:00.000Z"),
        "weekly",
      );
    });

    expect(api.updateTodo).toHaveBeenCalledWith("tok", "r1", {
      content: "Package",
      topic: "General",
      due_at: "2026-08-25T18:00:00.000Z",
      recurrence_rule: "weekly",
    });

    const optimistic = setTodos.mock.calls[0][0] as (prev: Todo[]) => Todo[];
    expect(optimistic([existing])[0]?.due_at).not.toBe(existing.due_at);
    const rollback = setTodos.mock.calls.at(-1)?.[0] as (prev: Todo[]) => Todo[];
    expect(rollback(optimistic([existing]))).toEqual([existing]);
  });

  it("turns a dated reminder into a plain to-do", async () => {
    const existing = todo({
      id: "r2",
      content: "Package",
      due_at: "2026-08-23T18:00:00.000Z",
      recurrence_rule: "weekly",
    });
    (api.updateTodo as jest.Mock).mockResolvedValue({
      ...existing,
      due_at: null,
      recurrence_rule: null,
    });
    await act(async () => {
      render(<Probe todos={[existing]} />);
    });
    await act(async () => {
      actions.openTodoEditor(existing);
    });
    await act(async () => {
      await actions.handleUpdateTodo(existing, "Package", null, "weekly");
    });
    expect(api.updateTodo).toHaveBeenCalledWith("tok", "r2", {
      content: "Package",
      topic: "General",
      due_at: null,
      recurrence_rule: null,
    });
  });
});
