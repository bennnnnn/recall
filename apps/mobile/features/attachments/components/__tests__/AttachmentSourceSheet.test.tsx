import { fireEvent, render } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import { AttachmentSourceSheet } from "@/features/attachments/components/AttachmentSourceSheet";

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

describe("AttachmentSourceSheet", () => {
  it("offers scan math plus camera, photo, and file", async () => {
    const onSelect = jest.fn();
    const { queryByText, getByText } = await render(
      <AttachmentSourceSheet visible onClose={jest.fn()} onSelect={onSelect} />,
    );

    expect(queryByText("chat.attach_generate_image")).toBeNull();
    expect(queryByText("chat.attach_library")).toBeNull();
    expect(getByText("chat.attach_solve_math_camera")).toBeTruthy();

    await fireEvent.press(getByText("chat.attach_camera"));
    expect(onSelect).toHaveBeenCalledWith("camera");
  });

  it("keeps File above the composer instead of under the bar", async () => {
    const composerClearance = 96;
    const { getByTestId, getByText } = await render(
      <AttachmentSourceSheet
        visible
        bottomOffset={composerClearance}
        onClose={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    expect(getByText("chat.attach_file")).toBeOnTheScreen();
    const panel = StyleSheet.flatten(getByTestId("app-sheet-dialog").props.style);
    expect(panel.marginBottom).toBeGreaterThanOrEqual(composerClearance);
  });
});
