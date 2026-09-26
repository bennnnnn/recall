import { memo, useMemo } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { Icon } from "@/ui/icons/Icon";
import Swipeable from "react-native-gesture-handler/ReanimatedSwipeable";
import { useTranslation } from "react-i18next";

import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import type { Todo } from "@/lib/api";
import { formatClockTime, formatMonthDayYear, formatShortWeekdayDate } from "@/lib/datetime/format";
import { categoryText } from "@/features/todos/model/todoCategories";
import type { TodoSection } from "@/features/todos/model/todoListRows";
import { notifyWarning, selection } from "@/lib/haptics";
import { useTheme } from "@/lib/theme";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  todo: Todo;
  section: TodoSection;
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

function completedMeta(iso: string | null | undefined, locale: string): string | null {
  if (!iso) return null;
  const done = new Date(iso);
  if (Number.isNaN(done.getTime())) return null;
  return `${formatMonthDayYear(done, locale)} · ${formatClockTime(done, locale)}`;
}

export const TodoRow = memo(function TodoRow({
  todo,
  section,
  busy,
  highlighted,
  onToggle,
  onOpen,
  onDelete,
  selecting = false,
  selected = false,
  onSelect,
}: Props) {
  const { t, i18n } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const locale = i18n.language;
  const due = todo.due_at ? new Date(todo.due_at) : null;
  const dueOk = due != null && Number.isFinite(due.getTime());
  const choose = () => {
    selection();
    if (selecting) onSelect?.(todo);
    else onToggle(todo);
  };
  const handleDelete = () => {
    notifyWarning();
    onDelete(todo);
  };
  const marked = selecting ? selected : todo.checked;

  const meta = (() => {
    if (todo.checked) return completedMeta(todo.updated_at, locale);
    const parts: string[] = [];
    const category = categoryText(todo.topic, t);
    if (category) parts.push(category);
    if (section === "overdue" && dueOk && due) parts.push(formatShortWeekdayDate(due, locale));
    if (todo.recurrence_rule) parts.push(t(`todos.repeat_${todo.recurrence_rule}`));
    return parts.length ? parts.join(" · ") : null;
  })();

  const timeLabel = !todo.checked && dueOk && due ? formatClockTime(due, locale) : null;
  const timeTone =
    dueOk && due && (section === "overdue" || due.getTime() < Date.now())
      ? s.todoTimeOverdue
      : section === "today"
        ? s.todoTimeToday
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
            color={marked ? C.primary : C.textTertiary}
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
        accessibilityLabel={timeLabel ? `${todo.content}, ${timeLabel}` : todo.content}
      >
        <Text style={[s.todoText, todo.checked && s.todoDone]} numberOfLines={3}>
          {todo.content}
        </Text>
        {meta ? (
          <Text style={s.todoMeta} numberOfLines={1}>
            {meta}
          </Text>
        ) : null}
      </Pressable>
      {timeLabel ? (
        <Text style={[s.todoTime, timeTone]} numberOfLines={1}>
          {timeLabel}
        </Text>
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
      renderRightActions={() => (
        <Pressable
          style={s.swipeDeleteAction}
          onPress={handleDelete}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel={t("common.delete")}
        >
          <Icon name="trash" size={IconSize.sm} color={C.onPrimary} />
          <Text style={s.swipeDeleteText}>{t("common.delete")}</Text>
        </Pressable>
      )}
    >
      {row}
    </Swipeable>
  );
});
