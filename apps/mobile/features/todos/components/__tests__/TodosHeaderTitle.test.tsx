import { render } from "@testing-library/react-native";

import { TodosHeaderTitle } from "@/features/todos/components/TodosHeaderTitle";
import { Type } from "@/lib/type";

// The list is one list now: no line under the title names a view ("Today", "Completed").
it("draws the To-do title alone, as a header", async () => {
  const ui = await render(<TodosHeaderTitle />);
  expect(ui.getByText("drawer.reminders")).toBeTruthy();
  expect(ui.queryByText(/todos\.menu_/)).toBeNull();
  expect(ui.getByRole("header").props.accessibilityLabel).toBe("drawer.reminders");
});

it("never grows past the 44pt bar with Dynamic Type", async () => {
  const ui = await render(<TodosHeaderTitle />);
  const cap = ui.getByText("drawer.reminders").props.maxFontSizeMultiplier as number;
  expect(cap).toBeGreaterThan(0);
  expect(Type.navTitle.lineHeight * cap).toBeLessThanOrEqual(44);
});
