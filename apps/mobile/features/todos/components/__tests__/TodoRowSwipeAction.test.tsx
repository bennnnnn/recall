/**
 * A row's red Delete stays hidden behind it until the row is swiped. Gesture handler 3 no
 * longer hides a swipeable's actions itself, and the row's card is translucent.
 */
import { StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";

import { TodoRow } from "@/features/todos/components/TodoRow";
import type { Todo } from "@/lib/api";

let mockProgress = 0;
jest.mock("react-native-gesture-handler/ReanimatedSwipeable", () => {
  const { View: MockView } = jest.requireActual<typeof import("react-native")>("react-native");
  return function MockSwipeable({ children, renderRightActions }: {
    children: React.ReactNode;
    renderRightActions: (progress: { value: number }) => React.ReactNode;
  }) {
    return (
      <MockView>
        {children}
        {renderRightActions({ value: mockProgress })}
      </MockView>
    );
  };
});
jest.mock("@/lib/haptics", () => ({ selection: jest.fn() }));

const TODO = {
  id: "a", content: "Walk", topic: "General", checked: false, due_at: null, recurrence_rule: null,
  sort_order: null, chat_id: null, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
} as Todo;

async function deleteOpacity(progress: number) {
  mockProgress = progress;
  const view = await render(<TodoRow todo={TODO} section="today" onToggle={jest.fn()} onDelete={jest.fn()} />);
  return StyleSheet.flatten(view.getByLabelText("common.delete").parent?.props.style)?.opacity;
}

it.each([
  [0, 0],
  [0.4, 1],
  [1, 1],
])("draws Delete at opacity %p of the swipe as %p", async (progress, opacity) => {
  expect(await deleteOpacity(progress)).toBe(opacity);
});
