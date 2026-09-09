import { useMemo, type ReactElement } from "react";
import { RefreshControl, ScrollView } from "react-native";

import { makeTodosStyles } from "@/components/todos/todosStyles";
import { useTheme } from "@/lib/theme";

type Props = {
  showRemindersEmptyHero: boolean;
  error: boolean;
  listHeader: ReactElement;
  refreshing?: boolean;
  onRefresh?: () => void;
};

export function TodosScrollList({
  showRemindersEmptyHero,
  error,
  listHeader,
  refreshing = false,
  onRefresh,
}: Props) {
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);

  return (
    <ScrollView
      style={s.list}
      contentContainerStyle={showRemindersEmptyHero && !error ? s.listEmpty : undefined}
      keyboardShouldPersistTaps="handled"
      refreshControl={
        onRefresh ? (
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />
        ) : undefined
      }
    >
      {listHeader}
    </ScrollView>
  );
}
