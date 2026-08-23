import React from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useTodosListGroups } from "@/hooks/useTodosListGroups";
import type { Todo } from "@/lib/api";

const mockLoadListGroupOrder = jest.fn();
const mockSaveListGroupOrder = jest.fn();

jest.mock("@/lib/listGroupOrder", () => ({
  loadListGroupOrder: (...args: unknown[]) => mockLoadListGroupOrder(...args),
  saveListGroupOrder: (...args: unknown[]) => mockSaveListGroupOrder(...args),
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

let latest: ReturnType<typeof useTodosListGroups> | null = null;

function Probe({ todos }: { todos: Todo[] }) {
  latest = useTodosListGroups("user-1", todos, "General");
  return <Text>{latest.listGroups.map((g) => g.topic).join(",")}</Text>;
}

describe("useTodosListGroups", () => {
  beforeEach(() => {
    latest = null;
    mockLoadListGroupOrder.mockReset();
    mockSaveListGroupOrder.mockReset();
    mockSaveListGroupOrder.mockResolvedValue(undefined);
  });

  it("loads saved empty list names when there are no todos", async () => {
    mockLoadListGroupOrder.mockResolvedValue(["Shopping"]);
    await act(async () => {
      render(<Probe todos={[]} />);
    });
    await waitFor(() => {
      expect(latest?.listGroups.map((g) => g.topic)).toEqual(["Shopping"]);
    });
  });

  it("keeps a saved empty list when other lists have items", async () => {
    mockLoadListGroupOrder.mockResolvedValue(["Shopping", "Groceries"]);
    await act(async () => {
      render(<Probe todos={[todo({ id: "1", content: "Milk", topic: "Groceries" })]} />);
    });
    await waitFor(() => {
      expect(latest?.listGroups.map((g) => g.topic)).toEqual(["Shopping", "Groceries"]);
    });
  });
});
