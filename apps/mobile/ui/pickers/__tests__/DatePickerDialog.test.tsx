import { fireEvent, render } from "@testing-library/react-native";

import { DatePickerDialog } from "../DatePickerDialog";
import { DateTimePickerDialog } from "../DateTimePickerDialog";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: "en-US" } }),
}));

const hidden = { includeHiddenElements: true };
const parts = (date: Date) => [
  date.getFullYear(),
  date.getMonth(),
  date.getDate(),
  date.getHours(),
  date.getMinutes(),
];

async function open(props: Partial<Parameters<typeof DatePickerDialog>[0]> = {}) {
  const onConfirm = jest.fn();
  const onCancel = jest.fn();
  const view = await render(
    <DatePickerDialog
      visible
      value={new Date(2026, 8, 26, 8, 30)}
      onConfirm={onConfirm}
      onCancel={onCancel}
      {...props}
    />,
  );
  return { view, onConfirm, onCancel };
}

describe("DatePickerDialog", () => {
  it("opens on the value's month with the day selected", async () => {
    const { view } = await open();
    expect(view.getByText("September 2026", hidden)).toBeTruthy();
    expect(view.getByTestId("date-picker-headline", hidden)).toHaveTextContent("Sat, Sep 26");
    expect(view.getByTestId("date-picker-day-26", hidden).props.accessibilityState).toEqual({
      selected: true,
      disabled: false,
    });
  });

  it("returns the picked day with the original time of day", async () => {
    const { view, onConfirm } = await open();
    await fireEvent.press(view.getByTestId("date-picker-day-3", hidden));
    expect(view.getByTestId("date-picker-headline", hidden)).toHaveTextContent("Thu, Sep 3");
    await fireEvent.press(view.getByTestId("date-picker-ok", hidden));
    expect(parts(onConfirm.mock.calls[0][0])).toEqual([2026, 8, 3, 8, 30]);
  });

  it("moves between months with the arrows", async () => {
    const { view, onConfirm } = await open();
    await fireEvent.press(view.getByTestId("date-picker-next", hidden));
    expect(view.getByText("October 2026", hidden)).toBeTruthy();
    await fireEvent.press(view.getByTestId("date-picker-day-1", hidden));
    await fireEvent.press(view.getByTestId("date-picker-previous", hidden));
    await fireEvent.press(view.getByTestId("date-picker-previous", hidden));
    expect(view.getByText("August 2026", hidden)).toBeTruthy();
    await fireEvent.press(view.getByTestId("date-picker-ok", hidden));
    expect(parts(onConfirm.mock.calls[0][0])).toEqual([2026, 9, 1, 8, 30]);
  });

  it("greys out days and months outside the limits", async () => {
    const { view } = await open({
      minimumDate: new Date(2026, 8, 10),
      maximumDate: new Date(2026, 9, 15),
    });
    expect(view.getByTestId("date-picker-day-9", hidden).props.accessibilityState.disabled).toBe(true);
    expect(view.getByTestId("date-picker-day-10", hidden).props.accessibilityState.disabled).toBe(false);
    expect(view.getByTestId("date-picker-previous", hidden).props.accessibilityState).toEqual({ disabled: true });
    await fireEvent.press(view.getByTestId("date-picker-next", hidden));
    expect(view.getByTestId("date-picker-day-16", hidden).props.accessibilityState.disabled).toBe(true);
    expect(view.getByTestId("date-picker-next", hidden).props.accessibilityState).toEqual({ disabled: true });
  });

  it("starts inside the limits when the value is outside them", async () => {
    const { view } = await open({
      value: new Date(2026, 0, 1, 9, 0),
      minimumDate: new Date(2026, 8, 10),
    });
    expect(view.getByTestId("date-picker-headline", hidden)).toHaveTextContent("Thu, Sep 10");
  });

  it("jumps to another year from the year list", async () => {
    const { view, onConfirm } = await open();
    await fireEvent.press(view.getByTestId("date-picker-years-toggle", hidden));
    expect(view.getByTestId("date-picker-year-2026", hidden).props.accessibilityState).toEqual({ selected: true });
    expect(view.queryByTestId("date-picker-next", hidden)).toBeNull();
    await fireEvent.press(view.getByTestId("date-picker-year-2030", hidden));
    expect(view.getByText("September 2030", hidden)).toBeTruthy();
    await fireEvent.press(view.getByTestId("date-picker-day-14", hidden));
    await fireEvent.press(view.getByTestId("date-picker-ok", hidden));
    expect(parts(onConfirm.mock.calls[0][0])).toEqual([2030, 8, 14, 8, 30]);
  });

  it("cancels without a value", async () => {
    const { view, onConfirm, onCancel } = await open();
    await fireEvent.press(view.getByTestId("date-picker-day-3", hidden));
    await fireEvent.press(view.getByTestId("date-picker-cancel", hidden));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});

describe("DateTimePickerDialog", () => {
  it("asks for the day, then the time, and returns both", async () => {
    const onConfirm = jest.fn();
    const view = await render(
      <DateTimePickerDialog
        visible
        value={new Date(2026, 8, 26, 8, 30)}
        is24Hour
        onConfirm={onConfirm}
        onCancel={jest.fn()}
      />,
    );
    await fireEvent.press(view.getByTestId("date-time-picker-date-day-28", hidden));
    await fireEvent.press(view.getByTestId("date-time-picker-date-ok", hidden));
    await fireEvent(view.getByTestId("date-time-picker-time-dial", hidden), "accessibilityAction", {
      nativeEvent: { actionName: "increment" },
    });
    await fireEvent.press(view.getByTestId("date-time-picker-time-ok", hidden));
    expect(parts(onConfirm.mock.calls[0][0])).toEqual([2026, 8, 28, 9, 30]);
  });
});
