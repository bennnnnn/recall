import { fireEvent, render } from "@testing-library/react-native";

import { AttachmentSourceSheet } from "@/components/AttachmentSourceSheet";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
  selection: jest.fn(),
}));

jest.mock("@gorhom/bottom-sheet", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports -- jest.mock factory
  const React = require("react");
  // eslint-disable-next-line @typescript-eslint/no-require-imports -- jest.mock factory
  const { View } = require("react-native");

  const MockBottomSheetModal = React.forwardRef(function MockBottomSheetModal(
    {
      children,
      onDismiss,
    }: {
      children: React.ReactNode;
      onDismiss?: () => void;
    },
    ref: React.Ref<{ present: () => void; dismiss: () => void }>,
  ) {
    const [open, setOpen] = React.useState(false);
    React.useImperativeHandle(ref, () => ({
      present: () => setOpen(true),
      dismiss: () => {
        setOpen(false);
        onDismiss?.();
      },
    }));
    if (!open) return null;
    return <View testID="attachment-bottom-sheet">{children}</View>;
  });

  return {
    BottomSheetModal: MockBottomSheetModal,
    BottomSheetView: function MockBottomSheetView({
      children,
    }: {
      children: React.ReactNode;
    }) {
      return <View>{children}</View>;
    },
    BottomSheetBackdrop: function MockBottomSheetBackdrop() {
      return null;
    },
  };
});

describe("AttachmentSourceSheet", () => {
  it("no longer offers image generation (text intent + confirmation sheet only)", async () => {
    const onSelect = jest.fn();
    const { queryByText, getByText } = await render(
      <AttachmentSourceSheet visible onClose={jest.fn()} onSelect={onSelect} />,
    );

    expect(queryByText("chat.attach_generate_image")).toBeNull();

    await fireEvent.press(getByText("chat.attach_camera"));
    expect(onSelect).toHaveBeenCalledWith("camera");
  });
});
