import { fireEvent, render } from "@testing-library/react-native";

import { AttachmentSourceSheet } from "@/components/AttachmentSourceSheet";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

describe("AttachmentSourceSheet", () => {
  it("no longer offers image generation (text intent + confirmation sheet only)", async () => {
    const onSelect = jest.fn();
    const { queryByText, getByText } = await render(
      <AttachmentSourceSheet onSelect={onSelect} />,
    );

    expect(queryByText("chat.attach_generate_image")).toBeNull();

    // The remaining sources are still there.
    await fireEvent.press(getByText("chat.attach_camera"));
    expect(onSelect).toHaveBeenCalledWith("camera");
  });
});
