import { useMemo, type ReactElement } from "react";
import { RefreshControl } from "react-native";
import { FlashList } from "@shopify/flash-list";

import { makeTodosStyles } from "@/components/todos/todosStyles";
import { useTheme } from "@/lib/theme";

const EMPTY: readonly never[] = [];

type Props = {
  showRemindersEmptyHero: boolean;
  error: boolean;
  listHeader: ReactElement;
  refreshing?: boolean;
  onRefresh?: () => void;
};

export function TodosFlashList({
  showRemindersEmptyHero,
  error,
  listHeader,
  refreshing = false,
  onRefresh,
}: Props) {
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);

  return (
    <FlashList
      style={s.list}
      data={EMPTY}
      renderItem={() => null}
      contentContainerStyle={showRemindersEmptyHero && !error ? s.listEmpty : undefined}
      keyboardShouldPersistTaps="handled"
      ListHeaderComponent={listHeader}
      refreshControl={
        onRefresh ? (
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />
        ) : undefined
      }
    />
  );
}
