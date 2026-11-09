/**
 * A drawer row's Share, Rename, Pin, Archive and Delete were reached only by a long-press: a
 * screen reader had no action for them, where the Library's tiles list theirs (2026-11-08).
 */
import { fireEvent, render, screen } from "@testing-library/react-native";

import {
  ChatRowActions,
  ConversationRow,
  makeConversationRowStyles,
} from "@/features/chat/drawer/ConversationRow";
import type { Chat } from "@/lib/api";
import { lightTheme } from "@/lib/theme";

const chat = { id: "c1", title: "Trip plan", pinned: false, archived: false } as Chat;
const rowStyles = makeConversationRowStyles(lightTheme);

async function row(props: Partial<Parameters<typeof ConversationRow>[0]> = {}, onAction = jest.fn()) {
  await render(
    <ChatRowActions.Provider value={onAction}>
      <ConversationRow chat={chat} onOpen={jest.fn()} onLongPress={jest.fn()} rowStyles={rowStyles} {...props} />
    </ChatRowActions.Provider>,
  );
  return { element: screen.getByLabelText(props.chat?.title ?? chat.title!), onAction };
}

const names = (element: { props: { accessibilityActions?: { name: string; label?: string }[] } }) =>
  element.props.accessibilityActions?.map((action) => `${action.name}:${action.label}`);

it("offers the long-press menu's actions and runs the one picked on its chat", async () => {
  const { element, onAction } = await row();
  expect(names(element)).toEqual([
    "share:chat.share",
    "rename:chat.rename",
    "pin:chat.pin",
    "archive:chat.archive",
    "delete:common.delete",
  ]);
  await fireEvent(element, "accessibilityAction", { nativeEvent: { actionName: "rename" } });
  expect(onAction).toHaveBeenCalledWith(chat, "rename");

  // A name the row did not offer (a platform's own) runs nothing.
  await fireEvent(element, "accessibilityAction", { nativeEvent: { actionName: "activate" } });
  expect(onAction).toHaveBeenCalledTimes(1);
});

it("follows the chat's state, as the menu does: Unpin, and no pin on an archived chat", async () => {
  const pinned = await row({ chat: { ...chat, pinned: true } });
  expect(names(pinned.element)).toContain("pin:chat.unpin");
  await screen.unmount();
  const archived = await row({ chat: { ...chat, archived: true } });
  expect(names(archived.element)).toEqual([
    "share:chat.share",
    "rename:chat.rename",
    "archive:chat.unarchive",
    "delete:common.delete",
  ]);
});

it("offers none while chats are being selected: the row is a checkbox then", async () => {
  const { element } = await row({ selectionMode: true, onToggleSelect: jest.fn() });
  expect(element.props.accessibilityActions).toBeUndefined();
});
