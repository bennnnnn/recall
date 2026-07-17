import { fireEvent, render } from "@testing-library/react-native";

import { AttachmentSourceSheet } from "@/components/AttachmentSourceSheet";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
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
    expect(getByText("chat.attach_solve_math_camera")).toBeTruthy();

    await fireEvent.press(getByText("chat.attach_camera"));
    expect(onSelect).toHaveBeenCalledWith("camera");
  });
});
