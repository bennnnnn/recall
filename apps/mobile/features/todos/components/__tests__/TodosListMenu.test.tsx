import { createRef } from "react";
import { render } from "@testing-library/react-native";

import { TodosListMenu } from "@/features/todos/components/TodosListMenu";

let mockItems: ({ key: string; label: string; onPress: () => void } | "separator")[] = [];
jest.mock("@/ui/overlay/Menu", () => ({
  Menu: (props: { items: typeof mockItems }) => {
    mockItems = props.items;
    return null;
  },
}));

// The views (All tasks, Not completed, Completed, Today) hid to-dos: Today opened on "Nothing
// due today" while undated ones existed. The list is one list; ⋯ only starts selecting.
it("offers Select tasks and no view to switch to", async () => {
  const onSelect = jest.fn();
  await render(<TodosListMenu visible anchorRef={createRef()} onSelect={onSelect} onClose={jest.fn()} />);
  expect(mockItems).toEqual([expect.objectContaining({ key: "select", label: "todos.menu_select" })]);
  const [select] = mockItems;
  if (select !== "separator") select?.onPress();
  expect(onSelect).toHaveBeenCalledTimes(1);
});
