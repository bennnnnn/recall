/**
 * The home's last-chat card is its title alone. The time beside it took the title's room
 * ("No Math Problem Fou… 10:42 AM", S23, 2026-11-08).
 */
import { fireEvent, render } from "@testing-library/react-native";

import { LastChatCard } from "@/features/chat/components/LastChatCard";

const mockSetParams = jest.fn();
const mockChat = {
  id: "chat-1",
  title: "Garden bed of ice plant flowers",
  updated_at: "2026-11-08T18:42:00.000Z",
  archived: false,
};

jest.mock("expo-router", () => ({
  useRouter: () => ({ setParams: mockSetParams }),
  useLocalSearchParams: () => ({}),
}));
// One list object, as the cache holds: a new one per read would never settle.
const mockList = { pinned: [], today: [mockChat], yesterday: [], last_7_days: [], this_month: [], older: [] };
jest.mock("@/features/chat/model/chatListCache", () => ({
  getCachedChatList: () => mockList,
  subscribeChatList: () => () => undefined,
}));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));

it("shows the last chat by its title, with no time, and opens it", async () => {
  const view = await render(<LastChatCard />);
  const card = view.getByTestId("home-last-chat");
  const words = card.queryAll((node) => typeof node.props.children === "string").map((node) => node.props.children);
  expect(words).toEqual(["Garden bed of ice plant flowers"]);
  fireEvent.press(card);
  expect(mockSetParams).toHaveBeenCalledWith({ chatId: "chat-1", highlightMessage: undefined });
});
