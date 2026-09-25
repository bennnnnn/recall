import { act, fireEvent, render } from "@testing-library/react-native";
import { Platform } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { TodoEditorSheet } from "@/features/todos/components/TodoEditorSheet";
import type { Todo } from "@/lib/api";

type Picker = { mode: string; value: Date; onChange: (event: DateTimePickerEvent, date?: Date) => void };
let mockPicker: Picker;
let mockForm: { onSave: () => void };
const mockT = (key: string) => key;
jest.mock("@react-native-community/datetimepicker", () => ({ __esModule: true, default: (props: Picker) => { mockPicker = props; return null; } }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: mockT }) }));
jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: { t: (key: string) => key },
  ensureLocale: jest.fn(),
}));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({}) }));
jest.mock("@/components/Icon", () => ({ Icon: () => null }));
jest.mock("@/lib/haptics", () => ({ selection: jest.fn() }));
jest.mock("@/features/todos/model/todoReminders", () => ({
  ensureNotificationPermission: jest.fn(async () => true),
}));
jest.mock("@/components/AppSheet", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    AppSheet: ({
      visible,
      children,
      overlay,
    }: {
      visible: boolean;
      children: React.ReactNode;
      overlay?: React.ReactNode;
    }) => (visible ? <View>{children}{overlay}</View> : null),
  };
});
jest.mock("@/components/SheetFormHeader", () => ({ SheetFormHeader: (props: typeof mockForm) => { mockForm = props; return null; } }));
const original = new Date(2026, 8, 4, 9, 30);
const todo = { id: "todo-a", content: "Call Mom", due_at: original.toISOString(), checked: false } as Todo;
function event(type: "set" | "dismissed", date = original): DateTimePickerEvent {
  return { type, nativeEvent: { timestamp: date.getTime(), utcOffset: 0 } };
}
function editProps(save = jest.fn(), extra: Record<string, unknown> = {}) {
  return {
    visible: true,
    saving: false,
    todos: [todo],
    editTodo: todo,
    onClose: jest.fn(),
    onSave: save,
    ...extra,
  };
}
beforeEach(() => { jest.clearAllMocks(); jest.replaceProperty(Platform, "OS", "android"); });
afterEach(() => jest.restoreAllMocks());

it("creates an Android reminder from separate date and time pickers", async () => {
  const save = jest.fn();
  const ui = await render(<TodoEditorSheet visible saving={false} todos={[]} onClose={jest.fn()} onSave={save} />);
  await fireEvent.changeText(ui.getByPlaceholderText("todos.todo_placeholder"), "Call Mom");
  await fireEvent.press(ui.getByLabelText("todos.add_date"));
  expect(mockPicker.mode).toBe("date");
  const day = new Date(2026, 9, 12, 9, 30);
  await act(() => { mockPicker.onChange(event("set", day), day); });
  await fireEvent.press(ui.getByLabelText("todos.time_label"));
  expect(mockPicker.mode).toBe("time");
  const time = new Date(2026, 8, 4, 17, 45);
  await act(() => { mockPicker.onChange(event("set", time), time); });
  await act(() => { mockForm.onSave(); });
  expect(save).toHaveBeenCalledWith("Call Mom", new Date(2026, 9, 12, 17, 45), null, "General");
});

it("creates a plain to-do without opening the date picker", async () => {
  const save = jest.fn();
  const ui = await render(
    <TodoEditorSheet visible saving={false} todos={[]} onClose={jest.fn()} onSave={save} />,
  );
  await fireEvent.changeText(ui.getByPlaceholderText("todos.todo_placeholder"), "Buy milk");
  await act(() => { mockForm.onSave(); });
  expect(save).toHaveBeenCalledWith("Buy milk", null, null, "General");
});

it("removes a date and its repeat rule together", async () => {
  const save = jest.fn();
  const repeating = { ...todo, recurrence_rule: "weekly" as const };
  const ui = await render(<TodoEditorSheet {...editProps(save)} editTodo={repeating} />);
  await fireEvent.press(ui.getByLabelText("todos.remove_date"));
  await act(() => { mockForm.onSave(); });
  expect(save).toHaveBeenCalledWith("Call Mom", null, null, "General");
});

it("edits the date and the time on separate Android pickers", async () => {
  const save = jest.fn();
  const ui = await render(<TodoEditorSheet {...editProps(save)} />);
  await fireEvent.press(ui.getByLabelText("todos.change_due"));
  expect(mockPicker.mode).toBe("date");
  const day = new Date(2026, 10, 2, 9, 30);
  await act(() => { mockPicker.onChange(event("set", day), day); });
  await fireEvent.press(ui.getByLabelText("todos.time_label"));
  expect(mockPicker.mode).toBe("time");
  const time = new Date(2026, 8, 4, 14, 15);
  await act(() => { mockPicker.onChange(event("set", time), time); });
  await act(() => { mockForm.onSave(); });
  expect(save).toHaveBeenCalledTimes(1);
  expect(save).toHaveBeenCalledWith("Call Mom", new Date(2026, 10, 2, 14, 15), null, "General");
});

it.each(["date", "time"] as const)("cancels an Android %s selection without changing the due date", async (step) => {
  const save = jest.fn();
  const ui = await render(<TodoEditorSheet {...editProps(save)} />);
  const label = step === "date" ? "todos.change_due" : "todos.time_label";
  await fireEvent.press(ui.getByLabelText(label));
  expect(mockPicker.mode).toBe(step);
  await act(() => { mockPicker.onChange(event("dismissed")); });
  await act(() => { mockForm.onSave(); });
  expect(save).toHaveBeenCalledWith("Call Mom", original, null, "General");
});

it("ignores a native callback after unmount", async () => {
  const save = jest.fn();
  const ui = await render(<TodoEditorSheet {...editProps(save)} />);
  await fireEvent.press(ui.getByLabelText("todos.change_due"));
  const callback = mockPicker.onChange;
  await ui.unmount();
  await act(() => { callback(event("set"), original); });
  expect(save).not.toHaveBeenCalled();
});

it("keeps the iOS spinner behind the date chip and commits on save", async () => {
  jest.replaceProperty(Platform, "OS", "ios");
  const save = jest.fn();
  const ui = await render(<TodoEditorSheet {...editProps(save)} />);
  // Chip-first: no picker until the chip is tapped.
  expect(ui.queryByLabelText("todos.change_due")).toBeOnTheScreen();
  await fireEvent.press(ui.getByLabelText("todos.change_due"));
  expect(mockPicker.mode).toBe("date");
  const moved = new Date(2026, 8, 5, 8, 0);
  await act(() => { mockPicker.onChange(event("set", moved), moved); });
  await fireEvent.press(ui.getByLabelText("todos.time_label"));
  expect(mockPicker.mode).toBe("time");
  await act(() => { mockPicker.onChange(event("set", moved), moved); });
  await act(() => { mockForm.onSave(); });
  expect(save).toHaveBeenCalledWith("Call Mom", moved, null, "General");
});

it("rejects an earlier reminder's picker callback after changing targets", async () => {
  const save = jest.fn();
  const props = editProps(save);
  const ui = await render(<TodoEditorSheet {...props} />);
  await fireEvent.press(ui.getByLabelText("todos.change_due"));
  await act(() => { mockPicker.onChange(event("set"), original); });
  const oldTime = mockPicker.onChange;
  const other = { ...todo, id: "todo-b" } as Todo;
  await ui.rerender(
    <TodoEditorSheet {...props} editTodo={other} />,
  );
  await fireEvent.press(ui.getByLabelText("todos.change_due"));
  await act(() => { oldTime(event("set"), original); });
  expect(mockPicker.mode).toBe("date");
  await act(() => { mockForm.onSave(); });
  expect(save).toHaveBeenCalledWith("Call Mom", original, null, "General");
});

it("ignores an already-open dialog callback while saving", async () => {
  const save = jest.fn();
  const props = editProps(save);
  const ui = await render(<TodoEditorSheet {...props} />);
  await fireEvent.press(ui.getByLabelText("todos.change_due"));
  await act(() => { mockPicker.onChange(event("set"), original); });
  const oldTime = mockPicker.onChange;
  await ui.rerender(<TodoEditorSheet {...props} saving />);
  await act(() => { oldTime(event("set"), original); });
  await act(() => { mockForm.onSave(); });
  expect(save).not.toHaveBeenCalled();
});

it("saves a repeat change from the edit sheet", async () => {
  const save = jest.fn();
  const ui = await render(<TodoEditorSheet {...editProps(save)} />);
  await fireEvent.press(ui.getByLabelText("todos.repeat_label, todos.repeat_none"));
  await fireEvent.press(ui.getByLabelText("todos.repeat_weekly"));
  await act(() => { mockForm.onSave(); });
  expect(save).toHaveBeenCalledWith("Call Mom", original, "weekly", "General");
});
