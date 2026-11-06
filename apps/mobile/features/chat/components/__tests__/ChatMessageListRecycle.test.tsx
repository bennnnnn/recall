import { render } from "@testing-library/react-native";
import { Text } from "react-native";

import { ChatMessageList } from "@/features/chat/components/ChatMessageList";
import type { Message } from "@/lib/api";
import { CHAT_RECYCLE_POOL } from "@/lib/messageListLayout";

const mockListProps = jest.fn();
jest.mock("@shopify/flash-list", () => ({
  FlashList: (props: Record<string, unknown>) => {
    mockListProps(props);
    return null;
  },
}));
jest.mock("@/features/home/components/HomeStarters", () => ({ HomeStarters: () => null }));
jest.mock("@/features/chat/components/LastChatCard", () => ({ LastChatCard: () => null }));

const message: Message = { id: "m1", role: "assistant", content: "a graph", model: null, created_at: "t" };

// A recycled row keeps drawing the message it last showed. With no limit, every row
// scrolled past kept its canvases, web views and photos in memory.
it("keeps only a few rows mounted off screen for reuse", async () => {
  await render(
    <ChatMessageList
      listRef={{ current: null }}
      messages={[message]}
      headerInset={0}
      listBottomPad={0}
      hasMoreOlder={false}
      loadingOlder={false}
      chatLoading={false}
      emptyHeight={100}
      renderItem={({ item }) => <Text>{item.content}</Text>}
      onLoadOlder={() => undefined}
      onScroll={() => undefined}
      onScrollEnd={() => undefined}
    />,
  );
  const props = mockListProps.mock.lastCall?.[0] as { maxItemsInRecyclePool?: number };
  expect(props.maxItemsInRecyclePool).toBe(CHAT_RECYCLE_POOL);
  expect(CHAT_RECYCLE_POOL).toBeLessThanOrEqual(4);
});
