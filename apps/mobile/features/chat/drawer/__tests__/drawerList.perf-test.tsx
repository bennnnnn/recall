/**
 * Render benchmarks for the drawer's chat list (`pnpm perf`, Reassure; CI compares a pull
 * request with main). Fifty chats under the drawer's headings, drawn by the shared FlashList
 * double, which mounts every row: what one row costs, fifty times. A new chat arriving at the
 * top must not redraw the rest (each row is memoized), so the second benchmark's time stays
 * close to the first's.
 */
import { useState } from "react";
import { Pressable, View } from "react-native";
import { fireEvent, screen } from "@testing-library/react-native";
import { measureRenders } from "reassure";

import { DrawerChatFlashList } from "@/features/chat/drawer/DrawerChatFlashList";
import type { Chat, ChatList } from "@/lib/api";

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 0 }));

const TITLES = [
  "Critical points of a cubic",
  "Plan my chemistry revision",
  "Python reminder app",
  "Which car for Addis roads",
  "Projectile launched at 30°",
  "Balancing a combustion equation",
  "Weekly meal plan on a budget",
  "Induction proof for a telescoping sum",
  "Cover letter for a lab internship",
  "Ohm's law with two resistors in parallel",
];

function chat(index: number, pinned = false): Chat {
  const day = String(1 + (index % 28)).padStart(2, "0");
  return {
    id: `chat-${index}`,
    // One untitled chat, as a first turn the title job has not reached yet leaves it.
    title: index === 7 ? null : TITLES[index % TITLES.length],
    model: "auto",
    pinned,
    created_at: `2026-10-${day}T09:00:00Z`,
    updated_at: `2026-10-${day}T09:00:00Z`,
  };
}

function chats(from: number, count: number, pinned = false): Chat[] {
  return Array.from({ length: count }, (_, offset) => chat(from + offset, pinned));
}

/** Fifty chats, filed as the drawer files them. */
const GROUPS: ChatList = {
  pinned: chats(0, 3, true),
  today: chats(3, 5),
  yesterday: chats(8, 6),
  last_7_days: chats(14, 12),
  this_month: chats(26, 12),
  older: chats(38, 12),
  archived: [],
};

const noop = () => undefined;
const expanded = () => false;
const HEADER = <View />;

function Drawer() {
  const [groups, setGroups] = useState(GROUPS);
  const newChat = () =>
    setGroups((current) => ({ ...current, today: [chat(100 + current.today.length), ...current.today] }));
  const { pinned, today, yesterday, last_7_days, this_month, older } = groups;
  const active = [pinned, today, yesterday, last_7_days, this_month, older];
  return (
    <>
      <Pressable testID="new-chat" onPress={newChat} />
      <DrawerChatFlashList
        groups={groups}
        activeChatCount={active.reduce((sum, list) => sum + list.length, 0)}
        loading={false}
        error={false}
        isSectionCollapsed={expanded}
        toggleSectionCollapsed={noop}
        activeChatId="chat-4"
        onOpenChat={noop}
        onOpenSearchResult={noop}
        onShowRowMenu={noop}
        listHeader={HEADER}
        contentPaddingTop={0}
        contentPaddingBottom={0}
        refreshing={false}
        onRefresh={noop}
      />
    </>
  );
}

test("drawer chat list with 50 chats", async () => {
  await measureRenders(<Drawer />);
});

test("drawer chat list as five new chats arrive", async () => {
  const scenario = async () => {
    for (let count = 0; count < 5; count += 1) {
      await fireEvent.press(screen.getByTestId("new-chat"));
    }
  };
  await measureRenders(<Drawer />, { scenario });
});
