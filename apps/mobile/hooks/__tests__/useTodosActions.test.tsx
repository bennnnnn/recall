import React from "react";
import { Alert, Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useTodosActions } from "@/hooks/useTodosActions";
import type { Todo } from "@/lib/api";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));

jest.mock("@/lib/todos/todoReminders", () => ({
  cancelTodoReminder: jest.fn(async () => undefined),
  ensureNotificationPermission: jest.fn(),
  syncTodoReminders: jest.fn(),
}));

jest.mock("@/lib/reminderSeen", () => ({
  markReminderIdsSeen: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  api: {
    deleteTodoTopic: jest.fn(),
    createTodo: jest.fn(),
    updateTodo: jest.fn(),
    deleteTodo: jest.fn(),
    reorderTodos: jest.fn(),
  },
}));

import { api } from "@/lib/api";

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

const persistGroupOrder = jest.fn(async () => undefined);
const setTodos = jest.fn();
const refresh = jest.fn(async () => undefined);

let actions: ReturnType<typeof useTodosActions>;

function Probe({ todos, groupOrder }: { todos: Todo[]; groupOrder: string[] }) {
  actions = useTodosActions({
    token: "tok",
    userId: "user-1",
    todos,
    setTodos,
    refresh,
    groupOrder,
    persistGroupOrder,
    goToDay: jest.fn(),
    isRemindersPage: false,
  });
  return <Text>todos actions</Text>;
}

async function confirmDelete() {
  const buttons = (Alert.alert as jest.Mock).mock.calls.at(-1)?.[2] as
    | { text: string; onPress?: () => void | Promise<void> }[]
    | undefined;
  const destructive = buttons?.find((b) => b.text === "common.delete");
  await act(async () => {
    await destructive?.onPress?.();
  });
}

describe("useTodosActions lists", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    persistGroupOrder.mockResolvedValue(undefined);
    (api.deleteTodoTopic as jest.Mock).mockResolvedValue(undefined);
    jest.spyOn(Alert, "alert").mockImplementation(() => {});
  });

  it("creates a list by appending to saved order", async () => {
    await act(async () => {
      render(<Probe todos={[]} groupOrder={["Groceries"]} />);
    });
    await act(async () => {
      await actions.handleCreateList("Shopping", () => undefined);
    });
    expect(persistGroupOrder).toHaveBeenCalledWith(["Groceries", "Shopping"]);
  });

  it("deletes an empty list without calling the topic API", async () => {
    await act(async () => {
      render(<Probe todos={[]} groupOrder={["Shopping"]} />);
    });
    actions.handleDeleteList("Shopping");
    await confirmDelete();
    expect(api.deleteTodoTopic).not.toHaveBeenCalled();
    expect(persistGroupOrder).toHaveBeenCalledWith([]);
  });

  it("deletes a list with only checked items via the topic API", async () => {
    await act(async () => {
      render(
        <Probe
          todos={[todo({ id: "1", content: "Milk", topic: "Groceries", checked: true })]}
          groupOrder={["Groceries"]}
        />,
      );
    });
    actions.handleDeleteList("Groceries");
    await confirmDelete();
    expect(api.deleteTodoTopic).toHaveBeenCalledWith("tok", "Groceries");
  });
});

describe("useTodosActions reminders", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    persistGroupOrder.mockResolvedValue(undefined);
    jest.spyOn(Alert, "alert").mockImplementation(() => {});
  });

  it("creates a reminder optimistically and closes the sheet before the API returns", async () => {
    let finish: (created: Todo) => void = () => undefined;
    (api.createTodo as jest.Mock).mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    const onCreated = jest.fn();
    const due = new Date("2026-08-24T18:00:00.000Z");
    await act(async () => {
      render(<Probe todos={[]} groupOrder={[]} />);
    });

    let createPromise: Promise<void> = Promise.resolve();
    await act(async () => {
      createPromise = actions.handleCreateReminder("Call mom", due, onCreated);
      await Promise.resolve();
    });

    expect(onCreated).toHaveBeenCalledTimes(1);
    expect(setTodos).toHaveBeenCalled();
    const addUpdater = setTodos.mock.calls[0][0] as (prev: Todo[]) => Todo[];
    const added = addUpdater([]);
    expect(added[0]).toMatchObject({
      content: "Call mom",
      due_at: due.toISOString(),
    });
    expect(added[0].id).toMatch(/^local-todo-/);
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
    const swapUpdater = setTodos.mock.calls.at(-1)?.[0] as (prev: Todo[]) => Todo[];
    expect(swapUpdater(added)[0]).toEqual(created);
  });

  it("rolls back an optimistic reminder when create fails", async () => {
    (api.createTodo as jest.Mock).mockRejectedValue(new Error("fail"));
    const onCreated = jest.fn();
    await act(async () => {
      render(<Probe todos={[]} groupOrder={[]} />);
    });

    await act(async () => {
      await actions.handleCreateReminder(
        "Call mom",
        new Date("2026-08-24T18:00:00.000Z"),
        onCreated,
      );
    });

    const addUpdater = setTodos.mock.calls[0][0] as (prev: Todo[]) => Todo[];
    const added = addUpdater([]);
    const rollback = setTodos.mock.calls.at(-1)?.[0] as (prev: Todo[]) => Todo[];
    expect(rollback(added)).toEqual([]);
    expect(Alert.alert).toHaveBeenCalled();
  });

  it("moves a due date immediately and rolls back on failure", async () => {
    (api.updateTodo as jest.Mock).mockRejectedValue(new Error("fail"));
    const existing = todo({
      id: "r1",
      content: "Package",
      due_at: "2026-08-23T18:00:00.000Z",
    });
    await act(async () => {
      render(<Probe todos={[existing]} groupOrder={[]} />);
    });

    await act(async () => {
      actions.openDuePicker(existing);
    });
    await act(async () => {
      actions.setDuePicker({
        todo: existing,
        date: new Date("2026-08-25T18:00:00.000Z"),
      });
    });
    await act(async () => {
      await actions.confirmDuePicker();
    });

    const optimistic = setTodos.mock.calls[0][0] as (prev: Todo[]) => Todo[];
    expect(optimistic([existing])[0]?.due_at).not.toBe(existing.due_at);
    expect(setTodos).toHaveBeenCalledWith([existing]);
  });
});
