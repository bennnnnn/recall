import { StyleSheet } from "react-native";
import { fireEvent, render } from "@testing-library/react-native";

import { DrawerFooter } from "@/features/chat/drawer/DrawerFooter";
import { makeConversationListStyles } from "@/features/chat/drawer/conversationListStyles";
import { lightTheme } from "@/lib/theme";

let mockUser: { name: string; avatar_url: string | null };
let mockToken: string;

jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ user: mockUser, token: mockToken }) }));
jest.mock("@/lib/config", () => ({ getApiUrl: () => "https://api.recall.test" }));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));

const props = {
  styles: makeConversationListStyles(lightTheme),
  theme: lightTheme,
  paddingBottom: 30,
  onAccount: jest.fn(),
  onNewChat: jest.fn(),
};

beforeEach(() => {
  jest.clearAllMocks();
  mockUser = { name: "Bini Recall", avatar_url: null };
  mockToken = "test-token";
});

// The owner's layout (2026-11-11): the account at the bottom left, opening Settings; New chat
// at the bottom right; no separate settings button.
it("shows the account at the left, which opens Settings", async () => {
  const view = await render(<DrawerFooter {...props} />);

  expect(view.getByText("BR")).toBeTruthy();
  expect(view.getByText("Bini Recall")).toBeTruthy();
  await fireEvent.press(view.getByRole("button", { name: "Bini Recall" }));
  expect(props.onAccount).toHaveBeenCalledTimes(1);
  expect(props.onNewChat).not.toHaveBeenCalled();
});

it("starts a new chat from the right", async () => {
  const view = await render(<DrawerFooter {...props} />);

  await fireEvent.press(view.getByRole("button", { name: "chat.new_chat" }));
  expect(props.onNewChat).toHaveBeenCalledTimes(1);
  expect(props.onAccount).not.toHaveBeenCalled();
  expect(view.queryByRole("button", { name: "settings.title" })).toBeNull();
});

it("rests on the home indicator as a solid bar", async () => {
  const view = await render(<DrawerFooter {...props} />);
  expect(StyleSheet.flatten(view.getByTestId("drawer-footer").props.style)).toMatchObject({
    bottom: 0,
    paddingBottom: 30,
    backgroundColor: lightTheme.bg,
  });
});

it("updates the photo and its credentials when the account changes", async () => {
  const footer = () => <DrawerFooter {...props} />;
  const view = await render(footer());
  mockUser = {
    name: "Bini Recall",
    avatar_url: "/attachments/11111111-1111-4111-8111-111111111111/file",
  };
  mockToken = "refreshed-token";
  await view.rerender(footer());

  expect(view.queryByText("BR")).toBeNull();
  expect(view.getByTestId("avatar-image").props.source).toEqual({
    uri: "https://api.recall.test/attachments/11111111-1111-4111-8111-111111111111/file",
    headers: { Authorization: "Bearer refreshed-token" },
  });
});
