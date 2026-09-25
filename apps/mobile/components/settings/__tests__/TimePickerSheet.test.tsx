import { act, render } from "@testing-library/react-native";
import { Platform } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";

import { TimePickerSheet } from "@/components/settings/TimePickerSheet";

type PickerProps = {
  mode: string;
  display: string;
  value: Date;
  onChange: (event: DateTimePickerEvent, date?: Date) => void;
};

let picker: PickerProps;
let header: {
  title: string;
  cancelLabel: string;
  saveLabel: string;
  onCancel: () => void;
  onSave: () => void;
  saving: boolean;
};

jest.mock("@react-native-community/datetimepicker", () => ({
  __esModule: true,
  default: (props: PickerProps) => {
    picker = props;
    return null;
  },
}));
jest.mock("@/ui/overlay/Sheet", () => ({
  Sheet: ({
    visible,
    children,
  }: {
    visible: boolean;
    children: React.ReactNode;
  }) => (visible ? children : null),
}));
jest.mock("@/ui/overlay/SheetFormHeader", () => ({
  SheetFormHeader: (props: typeof header) => {
    header = props;
    return null;
  },
}));

function event(type: "set" | "dismissed", date: Date): DateTimePickerEvent {
  return {
    type,
    nativeEvent: { timestamp: date.getTime(), utcOffset: 0 },
  };
}

const baseProps = {
  visible: true,
  title: "Quiet hours start",
  valueMinutes: 22 * 60,
  cancelLabel: "Cancel",
  saveLabel: "Done",
};

beforeEach(() => {
  jest.clearAllMocks();
  jest.replaceProperty(Platform, "OS", "ios");
});

afterEach(() => jest.restoreAllMocks());

it("keeps iOS spinner changes as a draft until Done", async () => {
  const onSave = jest.fn();
  const changed = new Date(2026, 8, 8, 23, 45);
  await render(
    <TimePickerSheet
      {...baseProps}
      onClose={jest.fn()}
      onSave={onSave}
    />,
  );

  expect(picker.mode).toBe("time");
  expect(picker.display).toBe("spinner");
  expect(header.title).toBe("Quiet hours start");
  expect(header.cancelLabel).toBe("Cancel");
  expect(header.saveLabel).toBe("Done");
  await act(() => picker.onChange(event("set", changed), changed));
  expect(onSave).not.toHaveBeenCalled();

  await act(() => header.onSave());
  expect(onSave).toHaveBeenCalledTimes(1);
  expect(onSave).toHaveBeenCalledWith(23 * 60 + 45);
});

it.each([
  ["set", 1],
  ["dismissed", 0],
] as const)("handles an Android %s event once", async (type, saveCount) => {
  jest.replaceProperty(Platform, "OS", "android");
  const onClose = jest.fn();
  const onSave = jest.fn();
  const changed = new Date(2026, 8, 8, 6, 15);
  await render(
    <TimePickerSheet
      {...baseProps}
      onClose={onClose}
      onSave={onSave}
    />,
  );

  expect(picker.display).toBe("default");
  await act(() => picker.onChange(event(type, changed), changed));
  expect(onClose).toHaveBeenCalledTimes(1);
  expect(onSave).toHaveBeenCalledTimes(saveCount);
  if (saveCount) expect(onSave).toHaveBeenCalledWith(6 * 60 + 15);
});
