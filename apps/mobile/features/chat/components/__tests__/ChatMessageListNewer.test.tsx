import { fireEvent, render, screen } from "@testing-library/react-native";
import { Text } from "react-native";

import { ChatMessageList } from "@/features/chat/components/ChatMessageList";
import type { Message } from "@/lib/api";

jest.mock("@/features/home/components/HomeContent", () => ({ HomeContent: () => null }));
jest.mock("@/features/chat/components/LastChatCard", () => ({ LastChatCard: () => null }));

const message: Message = { id: "m1", role: "user", content: "hello", model: null, created_at: "t" };

function list(
  newerPage: { loading: boolean; load: () => Promise<void> } | null,
  older: { hasMoreOlder: boolean; loadingOlder: boolean } = { hasMoreOlder: false, loadingOlder: false },
) {
  return (
    <ChatMessageList
      listRef={{ current: null }}
      messages={[message]}
      headerInset={0}
      listBottomPad={0}
      hasMoreOlder={older.hasMoreOlder}
      loadingOlder={older.loadingOlder}
      newerPage={newerPage}
      chatLoading={false}
      emptyHeight={100}
      renderItem={({ item }) => <Text>{item.content}</Text>}
      onLoadOlder={() => undefined}
      onScroll={() => undefined}
      onScrollEnd={() => undefined}
    />
  );
}

it("offers the next page below a window around a search hit (NET-18)", async () => {
  const load = jest.fn(async () => undefined);
  await render(list({ loading: false, load }));
  await fireEvent.press(screen.getByLabelText("chat.load_newer"));
  expect(load).toHaveBeenCalledTimes(1);
});

it("offers nothing below a thread that ends at the newest message", async () => {
  await render(list(null));
  expect(screen.queryByLabelText("chat.load_newer")).toBeNull();
});

// It showed "…" under its old name: a screen reader heard "Load earlier messages" while it loaded.
it("says a page is loading, as text and as a busy state, earlier and newer alike", async () => {
  await render(list({ loading: true, load: jest.fn() }, { hasMoreOlder: true, loadingOlder: true }));
  for (const name of ["chat.loading_earlier", "chat.loading_newer"]) {
    const button = screen.getByRole("button", { name });
    expect(button.props.accessibilityState).toEqual({ busy: true, disabled: true });
    expect(screen.getByText(name)).toBeTruthy();
  }
  expect(screen.queryByText("…")).toBeNull();
});

it("names the page it loads while idle", async () => {
  await render(list({ loading: false, load: jest.fn() }, { hasMoreOlder: true, loadingOlder: false }));
  expect(screen.getByRole("button", { name: "chat.load_earlier" }).props.accessibilityState).toEqual({
    busy: false,
    disabled: false,
  });
});
