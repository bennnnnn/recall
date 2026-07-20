import { fireEvent, render } from "@testing-library/react-native";

import { ChatActionsSheet } from "@/components/ChatActionsSheet";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
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

  it("renders the floating AppSheet with a handle", async () => {
    const { getByTestId, getByText } = await render(<ChatActionsSheet {...baseProps} />);

    expect(getByTestId("app-sheet-handle")).toBeTruthy();
    expect(getByText("chat.share")).toBeTruthy();
    expect(getByText("Trip ideas")).toBeTruthy();
  });

  it("dismisses when the backdrop is pressed", async () => {
    const onClose = jest.fn();
    const { getByTestId } = await render(
      <ChatActionsSheet {...baseProps} onClose={onClose} />,
    );

    await fireEvent.press(getByTestId("app-sheet-backdrop"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows Select when onSelectChats is provided", async () => {
    const onSelectChats = jest.fn();
    const { getByText } = await render(
      <ChatActionsSheet {...baseProps} onSelectChats={onSelectChats} />,
    );

    expect(getByText("drawer.select")).toBeTruthy();
    await fireEvent.press(getByText("drawer.select"));
    expect(onSelectChats).toHaveBeenCalledTimes(1);
  });

  it("hides Select when onSelectChats is omitted", async () => {
    const { queryByText } = await render(<ChatActionsSheet {...baseProps} />);
    expect(queryByText("drawer.select")).toBeNull();
  });

  it("shows Models when onOpenModels is provided", async () => {
    const onOpenModels = jest.fn();
    const { getByText } = await render(
      <ChatActionsSheet {...baseProps} onOpenModels={onOpenModels} />,
    );

    expect(getByText("settings.model")).toBeTruthy();
    await fireEvent.press(getByText("settings.model"));
    expect(onOpenModels).toHaveBeenCalledTimes(1);
  });

  it("hides Models when onOpenModels is omitted", async () => {
    const { queryByText } = await render(<ChatActionsSheet {...baseProps} />);
    expect(queryByText("settings.model")).toBeNull();
  });
});
