/**
 * A new search's results go in above the chat rows, and FlashList keeps the rows on
 * screen, which pushed the results up out of sight. A new search shows from the top;
 * loading more results keeps the place.
 */
import { render } from "@testing-library/react-native";

import { DrawerChatFlashList } from "@/features/chat/drawer/DrawerChatFlashList";
import type { ChatList, SearchResult } from "@/lib/api";

const mockScrollToOffset = jest.fn();

jest.mock("@shopify/flash-list", () => {
  const { forwardRef, useImperativeHandle } = jest.requireActual<typeof import("react")>("react");
  return {
    FlashList: forwardRef(function MockFlashList(_props, ref) {
      useImperativeHandle(ref, () => ({ scrollToOffset: mockScrollToOffset }));
      return null;
    }),
  };
});

jest.mock("@/lib/api", () => ({}));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 0 }));

const groups = { pinned: [], today: [], yesterday: [], last_7_days: [], this_month: [], older: [], archived: [] } as unknown as ChatList;

const result = (id: string): SearchResult => ({
  match_type: "message",
  message_id: id,
  chat_id: `chat-${id}`,
  chat_title: null,
  content: "rain",
  role: "user",
  created_at: "2026-01-01T00:00:00Z",
});

function list(searchResults: SearchResult[]) {
  return (
    <DrawerChatFlashList
      groups={groups}
      activeChatCount={0}
      loading={false}
      error={false}
      isSectionCollapsed={() => false}
      toggleSectionCollapsed={jest.fn()}
      onOpenChat={jest.fn()}
      onOpenSearchResult={jest.fn()}
      onShowRowMenu={jest.fn()}
      listHeader={<></>}
      contentPaddingTop={0}
      contentPaddingBottom={0}
      refreshing={false}
      onRefresh={jest.fn()}
      searchOpen
      searchResults={searchResults}
    />
  );
}

beforeEach(() => mockScrollToOffset.mockClear());

it("shows a new search's results from the top", async () => {
  const view = await render(list([]));
  expect(mockScrollToOffset).not.toHaveBeenCalled();

  await view.rerender(list([result("a"), result("b")]));
  expect(mockScrollToOffset).toHaveBeenCalledTimes(1);
  expect(mockScrollToOffset).toHaveBeenCalledWith({ offset: 0, animated: false });

  await view.rerender(list([result("c")]));
  expect(mockScrollToOffset).toHaveBeenCalledTimes(2);
});

it("keeps the place when more results load below", async () => {
  const view = await render(list([result("a")]));
  mockScrollToOffset.mockClear();

  await view.rerender(list([result("a"), result("b"), result("c")]));
  expect(mockScrollToOffset).not.toHaveBeenCalled();
});
