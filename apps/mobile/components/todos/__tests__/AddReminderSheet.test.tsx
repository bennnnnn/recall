import type { ReactNode } from "react";
import { fireEvent, render } from "@testing-library/react-native";

import { AddReminderSheet } from "@/components/todos/AddReminderSheet";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/lib/reduceMotion", () => ({
  useReduceMotion: () => false,
}));

jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
  selection: jest.fn(),
}));

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

jest.mock("@react-native-community/datetimepicker", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    __esModule: true,
    default: () => <View testID="datetime-picker" />,
  };
});

jest.mock("@/components/AppSheet", () => {
  const { View: RNView } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    AppSheet: ({
      children,
      visible,
    }: {
      children: ReactNode;
      visible: boolean;
    }) => (visible ? <RNView>{children}</RNView> : null),
  };
});

describe("AddReminderSheet", () => {
  it("picks one repeat type from a popup list", async () => {
    const { getByLabelText, queryByLabelText } = await render(
      <AddReminderSheet
        visible
        saving={false}
        todos={[]}
        onClose={jest.fn()}
        onSave={jest.fn()}
      />,
    );

    const field = getByLabelText("todos.repeat_label, todos.repeat_none");
    expect(queryByLabelText("todos.repeat_weekly")).toBeNull();

    await fireEvent.press(field);
    expect(getByLabelText("todos.repeat_weekly").props.accessibilityRole).toBe("radio");

    await fireEvent.press(getByLabelText("todos.repeat_weekly"));
    expect(getByLabelText("todos.repeat_label, todos.repeat_weekly")).toBeTruthy();
    expect(queryByLabelText("todos.repeat_monthly")).toBeNull();
  });
});
