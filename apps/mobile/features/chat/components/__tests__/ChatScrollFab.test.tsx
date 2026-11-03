import { StyleSheet } from "react-native";
import { fireEvent, render } from "@testing-library/react-native";

import {
  ChatScrollFab,
  SCROLL_FAB_SIZE,
  SCROLL_FAB_TARGET,
} from "@/features/chat/components/ChatScrollFab";
import { tap } from "@/lib/haptics";

jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));

it("taps once and scrolls when pressed", async () => {
  const onPress = jest.fn();
  const view = await render(<ChatScrollFab visible bottomOffset={80} scrollAwayCount={3} onPress={onPress} />);
  await fireEvent.press(view.getByRole("button", { name: "chat.scroll_to_latest" }));
  expect(onPress).toHaveBeenCalledTimes(1);
  expect(tap).toHaveBeenCalledTimes(1);
});

// A tap on the button moved a calculator card's slider under it: the button sat in a
// full-width strip that passed touches on, and owned only its drawn circle.
it("owns its whole square over the messages, not just the drawn circle", async () => {
  const view = await render(<ChatScrollFab visible bottomOffset={80} scrollAwayCount={0} onPress={jest.fn()} />);
  const slot = view.getByTestId("chat-scroll-fab");
  const slotStyle = StyleSheet.flatten(slot.props.style);
  expect(slot.props.pointerEvents ?? "auto").toBe("auto");
  expect(slotStyle).toMatchObject({ width: SCROLL_FAB_TARGET, height: SCROLL_FAB_TARGET });
  expect(slotStyle.right).toBeUndefined();

  const target = StyleSheet.flatten(view.getByTestId("chat-scroll-fab-button").props.style);
  expect(target).toMatchObject({ width: SCROLL_FAB_TARGET, height: SCROLL_FAB_TARGET });
  expect(SCROLL_FAB_TARGET).toBeGreaterThan(SCROLL_FAB_SIZE);
});

it("keeps the drawn circle where the offset puts it", async () => {
  const view = await render(<ChatScrollFab visible bottomOffset={80} scrollAwayCount={0} onPress={jest.fn()} />);
  const slotStyle = StyleSheet.flatten(view.getByTestId("chat-scroll-fab").props.style);
  expect(slotStyle.bottom + (SCROLL_FAB_TARGET - SCROLL_FAB_SIZE) / 2).toBe(80);
});
