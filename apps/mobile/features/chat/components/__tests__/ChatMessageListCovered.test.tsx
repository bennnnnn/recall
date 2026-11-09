/**
 * Live talk's call is drawn over the thread, under the header: a screen reader swiped into
 * messages nobody could see. The real FlashList hands these props to its ScrollView; the shared
 * jest mock drops them, so this one keeps them.
 */
import { render, screen } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { Text } from "react-native";

import { ChatMessageList } from "@/features/chat/components/ChatMessageList";
import type { Message } from "@/lib/api";

jest.mock("@shopify/flash-list", () => {
  const { View: MockView } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    FlashList: (props: {
      data: Message[];
      renderItem: (info: { item: Message }) => ReactNode;
      accessibilityElementsHidden?: boolean;
      importantForAccessibility?: "auto" | "no-hide-descendants";
    }) => (
      <MockView
        testID="thread"
        accessibilityElementsHidden={props.accessibilityElementsHidden}
        importantForAccessibility={props.importantForAccessibility}
      >
        {props.data.map((item) => <MockView key={item.id}>{props.renderItem({ item })}</MockView>)}
      </MockView>
    ),
  };
});
jest.mock("@/features/home/components/HomeContent", () => ({ HomeContent: () => null }));
jest.mock("@/features/chat/components/LastChatCard", () => ({ LastChatCard: () => null }));

const message: Message = { id: "m1", role: "user", content: "hello", model: null, created_at: "t" };

function list(covered: boolean) {
  return (
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
      header={<Text>header</Text>}
      covered={covered}
    />
  );
}

it("hides the thread, not the header, from a screen reader while live talk covers it", async () => {
  await render(list(false));
  expect(screen.getByText("hello")).toBeTruthy();

  await screen.rerender(list(true));
  expect(screen.queryByText("hello")).toBeNull();
  expect(screen.getByText("hello", { includeHiddenElements: true })).toBeTruthy();
  expect(screen.getByText("header")).toBeTruthy();
});
