import { useTranslation } from "react-i18next";

import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { DrawerNavLinks } from "@/components/drawer/DrawerNavLinks";
import { DrawerSearchResults } from "@/components/drawer/DrawerSearchResults";
import type { ConversationListStyles } from "@/components/drawer/conversationListStyles";
import type { SearchResult } from "@/lib/api";
import type { Theme } from "@/lib/theme";

type Props = {
  styles: ConversationListStyles;
  theme: Theme;
  showIndicator: boolean;
  unseenCount: number;
  onProjects: () => void;
  onLists: () => void;
  onReminders: () => void;
  loading: boolean;
  error: boolean;
  activeChatCount: number;
  searchOpen: boolean;
  onRetry: () => void;
  hasSearchQuery: boolean;
  searchLoading: boolean;
  searchError: boolean;
  searchResults: SearchResult[];
  hasMore?: boolean;
  loadingMore?: boolean;
  onLoadMore?: () => void;
  onOpenChat: (chatId: string, messageId?: string | null) => void;
};

export function DrawerListHeader({
  styles: s,
  theme,
  showIndicator,
  unseenCount,
  onProjects,
  onLists,
  onReminders,
  loading,
  error,
  activeChatCount,
  searchOpen,
  onRetry,
  hasSearchQuery,
  searchLoading,
  searchError,
  searchResults,
  hasMore,
  loadingMore,
  onLoadMore,
  onOpenChat,
}: Props) {
  const { t } = useTranslation();

  return (
    <>
      <DrawerNavLinks
        styles={s}
        theme={theme}
        showIndicator={showIndicator}
        unseenCount={unseenCount}
        onProjects={onProjects}
        onLists={onLists}
        onReminders={onReminders}
      />
      {loading && activeChatCount === 0 && !searchOpen ? (
        <SkeletonList count={4} />
      ) : error && activeChatCount === 0 ? (
        <StateView
          variant="error"
          compact
          message={t("drawer.cant_reach")}
          onRetry={onRetry}
          retryLabel={t("common.retry")}
        />
      ) : null}
      {searchOpen ? (
        <DrawerSearchResults
          hasSearchQuery={hasSearchQuery}
          searchLoading={searchLoading}
          searchError={searchError}
          searchResults={searchResults}
          hasMore={hasMore}
          loadingMore={loadingMore}
          onLoadMore={onLoadMore}
          onOpenChat={onOpenChat}
        />
      ) : null}
    </>
  );
}
