import type { Todo } from "@/lib/api";
import {
  buildListGroups,
  displayGroupTitle,
  isDefaultListTopic,
  listGroupTopics,
  mergeGroupOrder,
  sortListItems,
} from "@/lib/listGroups";
import { DEFAULT_TOPIC } from "@/lib/todoTopics";

function todo(partial: Partial<Todo> & Pick<Todo, "id" | "content">): Todo {
  return {
    topic: DEFAULT_TOPIC,
    checked: false,
    due_at: null,
    sort_order: null,
    chat_id: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    ...partial,
  };
}

describe("buildListGroups", () => {
  it("groups list items by topic and splits open vs done", () => {
    const groups = buildListGroups(
      [
        todo({ id: "1", content: "Milk", topic: "Groceries" }),
        todo({ id: "2", content: "Eggs", topic: "Groceries", checked: true }),
        todo({ id: "3", content: "Report", topic: "Work" }),
        todo({
          id: "4",
          content: "Reminder",
          topic: "General",
          due_at: "2026-06-27T10:00:00.000Z",
        }),
      ],
      [],
      "General",
    );

    expect(groups).toHaveLength(2);
    const groceries = groups.find((g) => g.topic === "Groceries");
    expect(groceries?.open.map((i) => i.id)).toEqual(["1"]);
    expect(groceries?.done.map((i) => i.id)).toEqual(["2"]);
    expect(groups.every((g) => g.topic !== "General" || g.isDefault)).toBe(true);
  });

  it("respects saved group order then appends new topics", () => {
    const groups = buildListGroups(
      [
        todo({ id: "1", content: "A", topic: "Work" }),
        todo({ id: "2", content: "B", topic: "Groceries" }),
      ],
      ["Groceries", "Work"],
      "General",
    );

    expect(listGroupTopics(groups)).toEqual(["Groceries", "Work"]);
  });
});

describe("sortListItems", () => {
  it("orders by sort_order then created_at", () => {
    const sorted = sortListItems([
      todo({ id: "2", content: "B", sort_order: 2, created_at: "2026-01-02T00:00:00Z" }),
      todo({ id: "1", content: "A", sort_order: 1, created_at: "2026-01-03T00:00:00Z" }),
      todo({ id: "3", content: "C", sort_order: null, created_at: "2026-01-01T00:00:00Z" }),
    ]);

    expect(sorted.map((i) => i.id)).toEqual(["1", "2", "3"]);
  });
});

describe("displayGroupTitle", () => {
  it("uses the default label for the default topic", () => {
    expect(isDefaultListTopic(DEFAULT_TOPIC)).toBe(true);
    expect(displayGroupTitle(DEFAULT_TOPIC, "General")).toBe("General");
    expect(displayGroupTitle("Groceries", "General")).toBe("Groceries");
  });
});

describe("mergeGroupOrder", () => {
  it("drops removed topics and appends new ones", () => {
    expect(mergeGroupOrder(["Work", "Old"], ["Work", "Groceries"])).toEqual([
      "Work",
      "Groceries",
    ]);
  });
});
