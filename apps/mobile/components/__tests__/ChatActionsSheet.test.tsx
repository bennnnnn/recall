import { fireEvent, render } from "@testing-library/react-native";

import { ChatActionsSheet } from "@/components/ChatActionsSheet";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
  MaterialCommunityIcons: "MaterialCommunityIcons",
}));

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

const baseProps = {
  visible: true,
  title: "Trip ideas",
  pinned: false,
  archived: false,
  onClose: jest.fn(),
  onShare: jest.fn(),
  onRename: jest.fn(),
  onTogglePin: jest.fn(),
  onToggleArchive: jest.fn(),
  onDelete: jest.fn(),
};

describe("ChatActionsSheet", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the shared overflow menu for placement=menu", async () => {
    const { getByTestId, queryByTestId, getByText } = await render(
      <ChatActionsSheet {...baseProps} placement="menu" />,
    );

    expect(getByTestId("chat-actions-menu")).toBeTruthy();
    expect(queryByTestId("app-sheet-handle")).toBeNull();
    expect(getByText("chat.share")).toBeTruthy();
    expect(getByText("chat.pin")).toBeTruthy();
  });

  it("dismisses the menu when the transparent backdrop is pressed", async () => {
    const onClose = jest.fn();
    const { getByTestId } = await render(
      <ChatActionsSheet {...baseProps} placement="menu" onClose={onClose} />,
    );

    await fireEvent.press(getByTestId("chat-actions-menu-backdrop"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
