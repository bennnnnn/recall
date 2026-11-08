import { render } from "@testing-library/react-native";

import { TodosHeaderTitle } from "@/features/todos/components/TodosHeaderTitle";
import { Type } from "@/lib/type";

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

it("never grows past the 44pt bar with Dynamic Type", async () => {
  const ui = await render(<TodosHeaderTitle view="completed" />);
  const caps = ["drawer.reminders", "todos.menu_completed"].map(
    (text) => ui.getByText(text).props.maxFontSizeMultiplier as number,
  );
  expect(caps.every((cap) => cap > 0)).toBe(true);
  const tallest = Type.navTitle.lineHeight * caps[0]! + Type.caption.lineHeight * caps[1]!;
  expect(tallest).toBeLessThanOrEqual(44);
});
