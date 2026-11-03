import { fireEvent, render } from "@testing-library/react-native";

import { DrawerHeader } from "@/features/chat/drawer/DrawerHeader";
import { makeConversationListStyles } from "@/features/chat/drawer/conversationListStyles";
import { lightTheme } from "@/lib/theme";

let mockUser: { name: string; avatar_url: string | null };
let mockToken: string;

jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ user: mockUser, token: mockToken }) }));
jest.mock("@/lib/config", () => ({ getApiUrl: () => "https://api.recall.test" }));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));

const styles = makeConversationListStyles(lightTheme);
const headerProps = {
  styles,
  theme: lightTheme,
  paddingTop: 0,
  searchOpen: false,
  searchQuery: "",
  searchInputRef: { current: null },
  onSearchChange: jest.fn(),
  onCloseSearch: jest.fn(),
};

beforeEach(() => {
  mockUser = { name: "Bini Recall", avatar_url: null };
  mockToken = "test-token";
});

it("puts the profile and new chat at the top", async () => {
  const onSettings = jest.fn();
  const onNewChat = jest.fn();
  const view = await render(
    <DrawerHeader {...headerProps} onSettings={onSettings} onNewChat={onNewChat} />,
  );

  expect(view.getByText("BR")).toBeTruthy();
  await fireEvent.press(view.getByRole("button", { name: "settings.title" }));
  expect(onSettings).toHaveBeenCalledTimes(1);
  expect(onNewChat).not.toHaveBeenCalled();
  await fireEvent.press(view.getByRole("button", { name: "drawer.new_chat" }));
  expect(onNewChat).toHaveBeenCalledTimes(1);
});

it("updates the sidebar photo and its credentials when the account changes", async () => {
  const header = () => <DrawerHeader {...headerProps} onSettings={jest.fn()} onNewChat={jest.fn()} />;
  const view = await render(header());
  mockUser = {
    name: "Bini Recall",
    avatar_url: "/attachments/11111111-1111-4111-8111-111111111111/file",
  };
  mockToken = "refreshed-token";
  await view.rerender(header());

  expect(view.queryByText("BR")).toBeNull();
  expect(view.getByTestId("avatar-image").props.source).toEqual({
    uri: "https://api.recall.test/attachments/11111111-1111-4111-8111-111111111111/file",
    headers: { Authorization: "Bearer refreshed-token" },
  });
});
