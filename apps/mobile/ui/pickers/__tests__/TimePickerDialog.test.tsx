import { fireEvent, render } from "@testing-library/react-native";

import { TimePickerDialog } from "../TimePickerDialog";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: "en-US" } }),
}));

// 256 dial: center 128, outer ring 100 out, inner ring 60 out.
const CENTER = 128;
const at = (angle: number, radius = 100) => {
  const radians = (angle * Math.PI) / 180;
  return {
    nativeEvent: {
      locationX: CENTER + radius * Math.sin(radians),
      locationY: CENTER - radius * Math.cos(radians),
    },
  };
};
const hidden = { includeHiddenElements: true };

async function open(props: Partial<Parameters<typeof TimePickerDialog>[0]> = {}) {
  const onConfirm = jest.fn();
  const onCancel = jest.fn();
  const view = await render(
    <TimePickerDialog
      visible
      value={{ hour: 21, minute: 11 }}
      is24Hour={false}
      onConfirm={onConfirm}
      onCancel={onCancel}
      {...props}
    />,
  );
  return { view, onConfirm, onCancel };
}

describe("TimePickerDialog", () => {
  it("opens on the value with the hour box active", async () => {
    const { view } = await open();
    expect(view.getByText("picker.select_time", hidden)).toBeTruthy();
    const hour = view.getByTestId("time-picker-hour", hidden);
    expect(hour.props.accessibilityState).toEqual({ selected: true });
    expect(view.getByTestId("time-picker-pm", hidden).props.accessibilityState).toEqual({ checked: true });
    expect(view.getByTestId("time-picker-dial", hidden).props.accessibilityValue).toEqual({
      text: expect.stringMatching(/9:11/),
    });
  });

  it("picks an hour on the dial, then moves on to minutes", async () => {
    const { view, onConfirm } = await open();
    const dial = view.getByTestId("time-picker-dial", hidden);
    await fireEvent(dial, "responderGrant", at(90));
    await fireEvent(dial, "responderRelease", at(90));
    expect(view.getByTestId("time-picker-minute", hidden).props.accessibilityState).toEqual({ selected: true });
    await fireEvent(view.getByTestId("time-picker-dial", hidden), "responderGrant", at(90));
    await fireEvent(view.getByTestId("time-picker-dial", hidden), "responderMove", at(186));
    await fireEvent(view.getByTestId("time-picker-dial", hidden), "responderRelease", at(186));
    await fireEvent.press(view.getByTestId("time-picker-ok", hidden));
    // 3 o'clock keeps the evening; 186° is 31 minutes.
    expect(onConfirm).toHaveBeenCalledWith({ hour: 15, minute: 31 });
  });

  it("switches the day half with AM/PM", async () => {
    const { view, onConfirm } = await open();
    await fireEvent.press(view.getByTestId("time-picker-am", hidden));
    await fireEvent.press(view.getByTestId("time-picker-ok", hidden));
    expect(onConfirm).toHaveBeenCalledWith({ hour: 9, minute: 11 });
  });

  it("uses the inner ring for 00 and 13–23 on a 24-hour clock", async () => {
    const { view, onConfirm } = await open({ is24Hour: true, value: { hour: 8, minute: 0 } });
    expect(view.queryByTestId("time-picker-am", hidden)).toBeNull();
    expect(view.getByTestId("time-picker-hour", hidden).props.accessibilityLabel).toBe("picker.hour, 08");
    const dial = view.getByTestId("time-picker-dial", hidden);
    await fireEvent(dial, "responderGrant", at(60, 60));
    await fireEvent(dial, "responderRelease", at(60, 60));
    await fireEvent.press(view.getByTestId("time-picker-ok", hidden));
    expect(onConfirm).toHaveBeenCalledWith({ hour: 14, minute: 0 });
  });

  it("steps the dial with screen-reader actions", async () => {
    const { view, onConfirm } = await open();
    await fireEvent(view.getByTestId("time-picker-dial", hidden), "accessibilityAction", {
      nativeEvent: { actionName: "increment" },
    });
    await fireEvent.press(view.getByTestId("time-picker-ok", hidden));
    expect(onConfirm).toHaveBeenCalledWith({ hour: 22, minute: 11 });
  });

  it("takes a typed time and blocks OK while it is invalid", async () => {
    const { view, onConfirm } = await open();
    await fireEvent.press(view.getByTestId("time-picker-mode", hidden));
    expect(view.getByText("picker.enter_time", hidden)).toBeTruthy();
    const hour = view.getByTestId("time-picker-hour-input", hidden);
    expect(hour.props.value).toBe("9");
    await fireEvent.changeText(hour, "13");
    expect(view.getByText("picker.invalid_time", hidden)).toBeTruthy();
    expect(view.getByTestId("time-picker-ok", hidden).props.accessibilityState).toEqual({ disabled: true });
    await fireEvent.changeText(view.getByTestId("time-picker-hour-input", hidden), "7");
    await fireEvent.changeText(view.getByTestId("time-picker-minute-input", hidden), "45");
    await fireEvent.press(view.getByTestId("time-picker-ok", hidden));
    expect(onConfirm).toHaveBeenCalledWith({ hour: 19, minute: 45 });
  });

  it("keeps a typed time when switching back to the clock", async () => {
    const { view, onConfirm } = await open();
    await fireEvent.press(view.getByTestId("time-picker-mode", hidden));
    await fireEvent.changeText(view.getByTestId("time-picker-minute-input", hidden), "05");
    await fireEvent.press(view.getByTestId("time-picker-mode", hidden));
    expect(view.getByTestId("time-picker-dial", hidden)).toBeTruthy();
    await fireEvent.press(view.getByTestId("time-picker-ok", hidden));
    expect(onConfirm).toHaveBeenCalledWith({ hour: 21, minute: 5 });
  });

  it("cancels without confirming, and OK does not also cancel", async () => {
    const first = await open();
    await fireEvent.press(first.view.getByTestId("time-picker-cancel", hidden));
    expect(first.onCancel).toHaveBeenCalledTimes(1);
    expect(first.onConfirm).not.toHaveBeenCalled();
    await first.view.unmount();

    const second = await open();
    await fireEvent.press(second.view.getByTestId("time-picker-ok", hidden));
    expect(second.onConfirm).toHaveBeenCalledWith({ hour: 21, minute: 11 });
    expect(second.onCancel).not.toHaveBeenCalled();
  });
});
