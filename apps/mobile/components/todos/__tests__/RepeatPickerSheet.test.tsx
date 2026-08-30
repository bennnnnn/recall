import { fireEvent, render } from "@testing-library/react-native";

import { RepeatPickerSheet } from "@/components/todos/RepeatPickerSheet";
import { selection } from "@/lib/haptics";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
  selection: jest.fn(),
}));

describe("RepeatPickerSheet", () => {
  it("lists each repeat type and reports the pick", async () => {
    const onSelect = jest.fn();
    const { getByLabelText } = await render(
      <RepeatPickerSheet selected={null} onSelect={onSelect} />,
    );

    expect(getByLabelText("todos.repeat_none").props.accessibilityState).toEqual(
      expect.objectContaining({ selected: true }),
    );
    expect(getByLabelText("todos.repeat_daily").props.accessibilityRole).toBe("radio");
    expect(getByLabelText("todos.repeat_weekdays")).toBeTruthy();
    expect(getByLabelText("todos.repeat_weekly")).toBeTruthy();
    expect(getByLabelText("todos.repeat_monthly")).toBeTruthy();

    await fireEvent.press(getByLabelText("todos.repeat_weekly"));
    expect(selection).toHaveBeenCalled();
    expect(onSelect).toHaveBeenCalledWith("weekly");
  });
});
