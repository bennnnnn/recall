import type { Chat, ChatList } from "@/lib/api";
import { activeChatsFromGroups, emptyChatList } from "@/lib/chatListSections";

/** Insert a chat into drawer groups if it is not already listed. */
export function insertChatIntoGroups(groups: ChatList, chat: Chat): ChatList {
  const listed = activeChatsFromGroups(groups).concat(groups.archived);
  if (listed.some((row) => row.id === chat.id)) {
    return groups;
  }

  if (chat.archived) {
    return { ...groups, archived: [chat, ...groups.archived] };
  }
  if (chat.pinned) {
    return { ...groups, pinned: [chat, ...groups.pinned] };
  }
  return { ...groups, today: [chat, ...groups.today] };
}

export { emptyChatList };
