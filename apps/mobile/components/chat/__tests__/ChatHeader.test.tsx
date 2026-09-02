import { fireEvent, render } from "@testing-library/react-native";

import { ChatHeader } from "@/components/chat/ChatHeader";
import { lightTheme as mockLightTheme } from "@/lib/theme";

const mockBack = jest.fn();
const mockReplace = jest.fn();
let mockPathname = "/";

jest.mock("expo-router", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({
    back: mockBack,
    canGoBack: () => true,
    replace: mockReplace,
  }),
}));

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
}));

jest.mock("expo-linear-gradient", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return { LinearGradient: View };
});

jest.mock("@/components/NewChatIcon", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return { NewChatIcon: () => <View testID="new-chat-icon" /> };
});

const props = {
  paddingTop: 47,
  height: 96,
  menuOverlayOpen: false,
  headerTitleLabel: "Trip",
  titleGenerating: false,
  chatTitle: "Trip",
  showIndicator: false,
  unseenCount: 0,
  hasMessages: true,
  onOpenDrawer: jest.fn(),
  onOpenReminders: jest.fn(),
  onNewChat: jest.fn(),
  onOpenMenu: jest.fn(),
};

describe("ChatHeader", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPathname = "/";
  });

  it("opens the drawer from home chat", async () => {
    const onOpenDrawer = jest.fn();
    const { getByLabelText } = await render(
      <ChatHeader {...props} onOpenDrawer={onOpenDrawer} />,
    );

    await fireEvent.press(getByLabelText("chat.open_drawer_a11y"));
    expect(onOpenDrawer).toHaveBeenCalled();
    expect(mockBack).not.toHaveBeenCalled();
  });

  it("goes back to Library from /open-chat", async () => {
    mockPathname = "/open-chat";
    const onOpenDrawer = jest.fn();
    const { getByLabelText, queryByLabelText } = await render(
      <ChatHeader {...props} onOpenDrawer={onOpenDrawer} />,
    );

    expect(queryByLabelText("chat.open_drawer_a11y")).toBeNull();
    await fireEvent.press(getByLabelText("common.back"));
    expect(mockBack).toHaveBeenCalled();
    expect(onOpenDrawer).not.toHaveBeenCalled();
  });
});
