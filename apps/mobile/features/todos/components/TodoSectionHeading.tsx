import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import type { TodoSection } from "@/features/todos/model/todoListRows";
import { formatDate } from "@/lib/datetime/format";
import { selection } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  section: TodoSection;
  dayKey?: string;
  /** The to-dos under it; Completed names its count, since it starts folded. */
  count: number;
  /** The list's first cell: more room above it. */
  first: boolean;
  completedOpen: boolean;
  onToggleCompleted: () => void;
};

/** The heading of a later day: its local noon (`localDayKey` read the day in the user's zone). */
function futureDayLabel(dayKey: string): string {
  const date = new Date(`${dayKey}T12:00:00`);
  if (!Number.isFinite(date.getTime())) return dayKey;
  return formatDate(date, "longWeekdayDate");
}

/**
 * A section's heading in the To-do list (Overdue, Today, Tomorrow, a later day, Anytime).
 * Completed is a button instead: "Completed · 3" opens and folds its to-dos in place, and
 * starts folded, so a long run of done ones stays out of the way.
 */
export function TodoSectionHeading({ section, dayKey, count, first, completedOpen, onToggleCompleted }: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const wrap = [s.sectionHeader, first && s.sectionHeaderFirst];

  if (section === "completed") {
    const name = t("todos.group_completed");
    return (
      <Pressable
        style={[wrap, styles.completed]}
        onPress={() => {
          selection();
          onToggleCompleted();
        }}
        accessibilityRole="button"
        accessibilityLabel={count > 0 ? `${name}, ${count}` : name}
        accessibilityHint={t(completedOpen ? "todos.completed_collapse_hint" : "todos.completed_expand_hint")}
        accessibilityState={{ expanded: completedOpen }}
        testID="todos-completed-heading"
      >
        <Text style={s.sectionHeading}>{count > 0 ? t("todos.group_completed_count", { count }) : name}</Text>
        <Icon name={completedOpen ? "chevron-up" : "chevron-down"} size={IconSize.xs} color={C.textSecondary} />
      </Pressable>
    );
  }
  const title = section === "date" && dayKey ? futureDayLabel(dayKey) : t(`todos.group_${section}`);
  const prominent = section === "today" || section === "overdue";
  return (
    <View style={wrap}>
      <Text style={prominent ? s.dayHeading : s.sectionHeading} accessibilityRole="header">{title}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  // A row the height of a touch target, its chevron after the words.
  completed: { flexDirection: "row", alignItems: "center", gap: Space.xxs, minHeight: Space.minTouch },
});
