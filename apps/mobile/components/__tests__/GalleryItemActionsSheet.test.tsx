import { fireEvent, render } from "@testing-library/react-native";

import { GalleryItemActionsSheet } from "@/components/gallery/GalleryItemActionsSheet";

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

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

describe("GalleryItemActionsSheet", () => {
  it("offers open chat, share, and delete when the item is linked", async () => {
    const onOpenChat = jest.fn();
    const onShare = jest.fn();
    const onDelete = jest.fn();
    const { getByText } = await render(
      <GalleryItemActionsSheet
        visible
        canOpenChat
        onClose={jest.fn()}
        onOpenChat={onOpenChat}
        onShare={onShare}
        onDelete={onDelete}
      />,
    );

    expect(getByText("gallery.open_chat")).toBeTruthy();
    expect(getByText("gallery.share")).toBeTruthy();
    expect(getByText("common.delete")).toBeTruthy();

    await fireEvent.press(getByText("gallery.open_chat"));
    expect(onOpenChat).toHaveBeenCalled();
  });

  it("hides open chat when the item has no chat", async () => {
    const { queryByText } = await render(
      <GalleryItemActionsSheet
        visible
        canOpenChat={false}
        onClose={jest.fn()}
        onOpenChat={jest.fn()}
        onShare={jest.fn()}
        onDelete={jest.fn()}
      />,
    );

    expect(queryByText("gallery.open_chat")).toBeNull();
    expect(queryByText("gallery.share")).toBeTruthy();
  });
});
