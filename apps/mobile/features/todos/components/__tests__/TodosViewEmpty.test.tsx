import { render } from "@testing-library/react-native";

import { TodosScrollList } from "@/features/todos/components/TodosScrollList";
import type { TodoView } from "@/features/todos/model/todoListFilter";

// A stand-in that draws the empty state when there are no cells, as FlashList does.
jest.mock("@shopify/flash-list", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  return {
    FlashList: ({ data, ListEmptyComponent }: { data: unknown[]; ListEmptyComponent: React.ReactNode }) =>
      data.length ? null : React.createElement(React.Fragment, null, ListEmptyComponent),
  };
});
jest.mock("react-native-gesture-handler/ReanimatedSwipeable", () => {
  const { View } = jest.requireActual("react-native");
  return { __esModule: true, default: View };
});
type StateProps = { variant: string; icon?: string; title?: string; message?: string };
const mockStates: StateProps[] = [];
jest.mock("@/ui/feedback/StateView", () => {
  const { Text } = jest.requireActual("react-native");
  return {
    StateView: (props: StateProps) => {
      mockStates.push(props);
      return <Text>{props.title}</Text>;
    },
  };
});

beforeEach(() => { mockStates.length = 0; });

function emptyView(view: TodoView, showEmpty = false) {
  const noop = jest.fn();
  return render(
    <TodosScrollList rows={[]} now={new Date()} showEmpty={showEmpty} view={view} error={false}
      listHeader={<></>} busyTodoIds={new Set()} onToggle={noop} onOpen={noop} onDeleteItem={noop} />,
  );
}

it.each([
  ["today", "todos.view_empty_today", "calendar"],
  ["open", "todos.view_empty_open", "check-circle"],
  ["completed", "todos.view_empty_completed", "circle"],
] as const)("an empty %s view says which view it is, with an icon and no body", async (view, title, icon) => {
  const ui = await emptyView(view);
  expect(ui.getByText(title)).toBeTruthy();
  expect(mockStates.at(-1)).toEqual({ variant: "empty", icon, title });
  expect(ui.queryByText("todos.filter_empty")).toBeNull();
});

it("leaves the empty list to the list header's hero when there are no to-dos at all", async () => {
  await emptyView("today", true);
  expect(mockStates).toEqual([]);
});
