import { memo, useMemo } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/ui/icons/Icon";
import Swipeable from "react-native-gesture-handler/ReanimatedSwipeable";
import Animated, { type SharedValue, useAnimatedStyle } from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import type { Todo } from "@/lib/api";
import { formatDate } from "@/lib/datetime/format";
import { categoryText } from "@/features/todos/model/todoCategories";
import { dueOfTodo, isDateOnly } from "@/features/todos/model/dueDate";
import type { TodoSection } from "@/features/todos/model/todoListRows";
import { selection } from "@/lib/haptics";
import { useTheme } from "@/lib/theme";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  todo: Todo;
  section: TodoSection;
  /** Its due time has passed on the to-do clock. The row is memoized: read in render,
   * the clock stayed at the last render's time, and a time that fell due kept today's color. */
  pastDue?: boolean;
  busy?: boolean;
  highlighted?: boolean;
  /** Stable parent callbacks (take the todo) — avoid per-row closures that defeat memo. */
  onToggle: (todo: Todo) => void;
  onOpen?: (todo: Todo) => void;
  onDelete: (todo: Todo) => void;
  selecting?: boolean;
  selected?: boolean;
  onSelect?: (todo: Todo) => void;
};

/**
 * The red Delete behind a row. Gesture handler 3 no longer hides a row's actions until it is
 * swiped, and the row's card is translucent: unhidden, Delete showed through every row.
 */
function SwipeDeleteAction({ progress, busy, onDelete }: {
  progress: SharedValue<number>;
  busy?: boolean;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const shown = useAnimatedStyle(() => ({ opacity: progress.value === 0 ? 0 : 1 }));
  return (
    <Animated.View style={[actionStyles.wrap, shown]}>
      <Pressable
        style={s.swipeDeleteAction}
        onPress={onDelete}
        disabled={busy}
        accessibilityRole="button"
        accessibilityLabel={t("common.delete")}
      >
        <Icon name="trash" size={IconSize.sm} color={C.onPrimary} />
        <Text style={s.swipeDeleteText}>{t("common.delete")}</Text>
      </Pressable>
    </Animated.View>
  );
}

const actionStyles = StyleSheet.create({
  // A row, so the action stretches to the row's height.
  wrap: { flexDirection: "row" },
});

function completedMeta(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const done = new Date(iso);
  if (Number.isNaN(done.getTime())) return null;
  return `${formatDate(done, "monthDayYear")} · ${formatDate(done, "time")}`;
}

export const TodoRow = memo(function TodoRow({
  todo,
  section,
  pastDue = false,
  busy,
  highlighted,
  onToggle,
  onOpen,
  onDelete,
  selecting = false,
  selected = false,
  onSelect,
}: Props) {
  // Also re-renders this memoized row when the language or the phone's clock changes.
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const due = dueOfTodo(todo)?.date ?? null;
  const dueOk = due != null && Number.isFinite(due.getTime());
  const choose = () => {
    selection();
    if (selecting) onSelect?.(todo);
    else onToggle(todo);
  };
  // Delete asks first; the haptic plays once the delete lands (useTodosActions).
  const handleDelete = () => onDelete(todo);
  const marked = selecting ? selected : todo.checked;

  const meta = (() => {
    if (todo.checked) return completedMeta(todo.updated_at);
    const parts: string[] = [];
    const category = categoryText(todo.topic, t);
    if (category) parts.push(category);
    if (section === "overdue" && dueOk && due) parts.push(formatDate(due, "weekdayDate"));
    if (todo.recurrence_rule) parts.push(t(`todos.repeat_${todo.recurrence_rule}`));
    return parts.length ? parts.join(" · ") : null;
  })();

  // A date alone has no time to show: its day heading, or in Overdue the date, says when.
  const timeLabel = !todo.checked && dueOk && due && !isDateOnly(todo) ? formatDate(due, "time") : null;
  const overdue = !todo.checked && dueOk && (section === "overdue" || pastDue);
  // Spoken as drawn: the title, its time, and "overdue" where the danger mark shows.
  const spokenLabel = [todo.content, timeLabel, overdue && t("todos.row_overdue")].filter(Boolean).join(", ");
  // A lit row (opened from Home or a push, or picked to select) sits on primaryLight, where
  // danger ink is under 4.5:1 in every dark accent and light violet, and grey ink in four dark
  // accents. Its grey lines and its time take the text ink there (a time later today keeps
  // primary) and its empty checkbox the secondary ink; the danger mark says overdue in both
  // states, so lighting a row never reflows it.
  const lit = Boolean(highlighted) || selected;
  const timeTone = section === "today" && !overdue
    ? s.todoTimeToday
    : lit
      ? s.todoInkLit
      : overdue
        ? s.todoTimeOverdue
        : s.todoTimeLater;

  const row = (
    <View style={[s.todoRow, highlighted && s.todoRowHighlighted, selected && s.todoRowSelected]}>
      <Pressable
        onPress={choose}
        hitSlop={10}
        style={s.checkbox}
        disabled={busy}
        accessibilityRole="checkbox"
        accessibilityLabel={todo.content}
        accessibilityState={{ checked: todo.checked, disabled: busy, busy }}
      >
        {busy ? (
          <ActivityIndicator size="small" color={C.primary} />
        ) : (
          <Icon
            name={marked ? "check-circle-filled" : "circle"}
            size={IconSize.md}
            color={marked ? C.primary : lit ? C.textSecondary : C.textTertiary}
          />
        )}
      </Pressable>
      <Pressable
        style={s.todoMain}
        onPress={() => {
          selection();
          if (selecting) onSelect?.(todo);
          else onOpen?.(todo);
        }}
        disabled={busy}
        accessibilityRole="button"
        accessibilityLabel={spokenLabel}
      >
        <Text style={[s.todoText, todo.checked && s.todoDone, lit && s.todoInkLit]} numberOfLines={3}>
          {todo.content}
        </Text>
        {meta ? (
          <Text style={[s.todoMeta, lit && s.todoInkLit]} numberOfLines={1}>
            {meta}
          </Text>
        ) : null}
      </Pressable>
      {timeLabel || overdue ? (
        <View style={s.todoTimeWrap}>
          {overdue ? (
            <Icon name="alert-circle" size={IconSize.xs} color={C.danger} testID="todo-overdue-mark" />
          ) : null}
          {timeLabel ? <Text style={[s.todoTime, timeTone]} numberOfLines={1}>{timeLabel}</Text> : null}
        </View>
      ) : null}
    </View>
  );

  return (
    <Swipeable
      friction={2}
      rightThreshold={40}
      overshootRight={false}
      enabled={!busy && !selecting}
      containerStyle={s.swipeContainer}
      renderRightActions={(progress) => (
        <SwipeDeleteAction progress={progress} busy={busy} onDelete={handleDelete} />
      )}
    >
      {row}
    </Swipeable>
  );
});
