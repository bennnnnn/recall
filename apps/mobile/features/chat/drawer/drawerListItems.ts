import type { ChatListSectionKey } from "@/features/chat/model/listSections";
import type { Chat, SearchResult } from "@/lib/api";

/** One row of the drawer's list: a section title, a chat, a search result or a load-more. */
export type DrawerChatListItem =
  | {
      type: "sectionHeader";
      key: ChatListSectionKey;
      title: string;
      count: number;
      collapsible: boolean;
    }
  | { type: "row"; key: string; chat: Chat }
  | { type: "searchRow"; key: string; result: SearchResult; query: string; onOpen: (id: string, messageId?: string | null) => void }
  | {
      type: "searchLoadMore";
      key: "search-load-more";
      loadingMore: boolean;
      loadingMoreError: boolean;
      onLoadMore?: () => void;
    }
  | { type: "archivedMore"; key: "archived-more" };
