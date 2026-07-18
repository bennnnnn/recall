import { useTranslation } from "react-i18next";

import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { DrawerSearchResultsChrome } from "@/components/drawer/DrawerSearchResults";

type Props = {
  loading: boolean;
  error: boolean;
  activeChatCount: number;
  searchOpen: boolean;
  onRetry: () => void;
  hasSearchQuery: boolean;
  searchLoading: boolean;
  searchError: boolean;
  searchResultCount: number;
};

export function DrawerListHeader({
  loading,
  error,
  activeChatCount,
  searchOpen,
  onRetry,
  hasSearchQuery,
  searchLoading,
  searchError,
  searchResultCount,
}: Props) {
  const { t } = useTranslation();

  return (
    <>
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
        <DrawerSearchResultsChrome
          hasSearchQuery={hasSearchQuery}
          searchLoading={searchLoading}
          searchError={searchError}
          resultCount={searchResultCount}
        />
      ) : null}
    </>
  );
}
