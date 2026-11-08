import { render } from "@testing-library/react-native";

import { TodosHeaderTitle } from "@/features/todos/components/TodosHeaderTitle";

it("names the list's view under the To-do title, for screen readers too", async () => {
  const ui = await render(<TodosHeaderTitle view="today" />);
  expect(ui.getByText("drawer.reminders")).toBeTruthy();
  expect(ui.getByText("todos.menu_today")).toBeTruthy();
  expect(ui.getByRole("header").props.accessibilityLabel).toBe("drawer.reminders, todos.menu_today");
});

it("draws the title alone on a to-do's own page", async () => {
  const ui = await render(<TodosHeaderTitle view={null} />);
  expect(ui.getByText("drawer.reminders")).toBeTruthy();
  expect(ui.queryByText(/todos\.menu_/)).toBeNull();
  expect(ui.getByRole("header").props.accessibilityLabel).toBe("drawer.reminders");
});
