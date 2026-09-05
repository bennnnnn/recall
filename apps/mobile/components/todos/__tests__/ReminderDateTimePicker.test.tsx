import { act, fireEvent, render } from "@testing-library/react-native";
import { Platform } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { AddReminderSheet } from "@/components/todos/AddReminderSheet";
import { DuePickerModal } from "@/components/todos/DuePickerModal";
import type { Todo } from "@/lib/api";

type Picker = { mode: string; value: Date; onChange: (event: DateTimePickerEvent, date?: Date) => void };
let mockPicker: Picker;
let mockForm: { onSave: () => void };
const mockT = (key: string) => key;
jest.mock("@react-native-community/datetimepicker", () => ({ __esModule: true, default: (props: Picker) => { mockPicker = props; return null; } }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: mockT }) }));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({}) }));
jest.mock("@/components/Icon", () => ({ Icon: () => null }));
jest.mock("@/lib/haptics", () => ({ selection: jest.fn() }));
jest.mock("@/components/AppSheet", () => ({ AppSheet: ({ visible, children }: { visible: boolean; children: React.ReactNode }) => visible ? children : null }));
jest.mock("@/components/SheetFormHeader", () => ({ SheetFormHeader: (props: typeof mockForm) => { mockForm = props; return null; } }));
const original = new Date(2026, 8, 4, 9, 30);
const todo = { id: "todo-a", content: "Call Mom", due_at: original.toISOString(), checked: false } as Todo;
function event(type: "set" | "dismissed", date = original): DateTimePickerEvent {
  return { type, nativeEvent: { timestamp: date.getTime(), utcOffset: 0 } };
}
beforeEach(() => { jest.clearAllMocks(); jest.replaceProperty(Platform, "OS", "android"); });
afterEach(() => jest.restoreAllMocks());

it("creates an Android reminder by choosing a date then a time", async () => {
  const save = jest.fn();
  const ui = await render(<AddReminderSheet visible saving={false} todos={[]} onClose={jest.fn()} onSave={save} />);
  await fireEvent.changeText(ui.getByPlaceholderText("todos.reminder_placeholder"), "Call Mom");
  await fireEvent.press(ui.getByLabelText("todos.due_date_required"));
  expect(mockPicker.mode).toBe("date");
  const day = new Date(2026, 9, 12, 9, 30);
  await act(() => { mockPicker.onChange(event("set", day), day); });
  expect(mockPicker.mode).toBe("time");
  const time = new Date(2026, 8, 4, 17, 45);
  await act(() => { mockPicker.onChange(event("set", time), time); });
  await act(() => { mockForm.onSave(); });
  expect(save).toHaveBeenCalledWith("Call Mom", new Date(2026, 9, 12, 17, 45), null);
});

it("commits an Android due-date edit only after the time step", async () => {
  const change = jest.fn();
  await render(<DuePickerModal todos={[todo]} duePicker={{ todo, date: original }} onDismiss={jest.fn()} onChange={change} onConfirm={jest.fn()} />);
  expect(mockPicker.mode).toBe("date");
  const firstCallback = mockPicker.onChange;
  const day = new Date(2026, 10, 2, 9, 30);
  await act(() => { firstCallback(event("set", day), day); });
  expect(change).not.toHaveBeenCalled();
  expect(mockPicker.mode).toBe("time");
  await act(() => { firstCallback(event("dismissed")); });
  expect(change).not.toHaveBeenCalled();
  const time = new Date(2026, 8, 4, 14, 15);
  const secondCallback = mockPicker.onChange;
  await act(() => { secondCallback(event("set", time), time); secondCallback(event("set", time), time); });
  expect(change).toHaveBeenCalledTimes(1);
  expect(change.mock.calls[0][1]).toEqual(new Date(2026, 10, 2, 14, 15));
});

it.each(["date", "time"])("cancels Android %s selection without committing a due date", async (step) => {
  const change = jest.fn();
  await render(<DuePickerModal todos={[todo]} duePicker={{ todo, date: original }} onDismiss={jest.fn()} onChange={change} onConfirm={jest.fn()} />);
  if (step === "time") await act(() => { mockPicker.onChange(event("set"), original); });
  await act(() => { mockPicker.onChange(event("dismissed")); });
  expect(change).toHaveBeenCalledTimes(1);
  expect(change.mock.calls[0][0].type).toBe("dismissed");
  expect(change.mock.calls[0][1]).toBeUndefined();
});

it("ignores a native callback after unmount", async () => {
  const change = jest.fn();
  const ui = await render(<DuePickerModal todos={[todo]} duePicker={{ todo, date: original }} onDismiss={jest.fn()} onChange={change} onConfirm={jest.fn()} />);
  const callback = mockPicker.onChange;
  await ui.unmount();
  await act(() => { callback(event("set"), original); });
  expect(change).not.toHaveBeenCalled();
});

it("retains the native combined picker on iOS", async () => {
  jest.replaceProperty(Platform, "OS", "ios");
  const change = jest.fn();
  await render(<DuePickerModal todos={[todo]} duePicker={{ todo, date: original }} onDismiss={jest.fn()} onChange={change} onConfirm={jest.fn()} />);
  expect(mockPicker.mode).toBe("datetime");
  await act(() => { mockPicker.onChange(event("set"), original); });
  expect(change).toHaveBeenCalledWith(event("set"), original);
});

it("rejects an earlier reminder's picker callback after changing targets", async () => {
  const change = jest.fn();
  const props = { todos: [todo], onDismiss: jest.fn(), onChange: change, onConfirm: jest.fn() };
  const ui = await render(<DuePickerModal {...props} duePicker={{ todo, date: original }} />);
  await act(() => { mockPicker.onChange(event("set"), original); });
  const oldTime = mockPicker.onChange;
  await ui.rerender(<DuePickerModal {...props} duePicker={{ todo: { ...todo, id: "todo-b" }, date: original }} />);
  await act(() => { oldTime(event("set"), original); });
  expect(change).not.toHaveBeenCalled();
  expect(mockPicker.mode).toBe("date");
});

it("ignores an already-open dialog callback while saving", async () => {
  const change = jest.fn();
  const props = { todos: [todo], duePicker: { todo, date: original }, onDismiss: jest.fn(), onChange: change, onConfirm: jest.fn() };
  const ui = await render(<DuePickerModal {...props} />);
  await act(() => { mockPicker.onChange(event("set"), original); });
  const oldTime = mockPicker.onChange;
  await ui.rerender(<DuePickerModal {...props} saving />);
  await act(() => { oldTime(event("set"), original); });
  expect(change).not.toHaveBeenCalled();
});
