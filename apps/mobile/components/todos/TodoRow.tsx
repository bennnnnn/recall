import { useMemo } from "react";
import { Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { makeTodosStyles } from "@/components/todos/todosStyles";
import type { Todo } from "@/lib/api";
import { describeDueAt } from "@/lib/dueDate";
import { useTheme } from "@/lib/theme";

export function TodoRow({
  todo,
  busy,
  highlighted,
  onToggle,
  onDue,
  onDelete,
  overlapWith,
}: {
  todo: Todo;
  busy?: boolean;
  highlighted?: boolean;
  onToggle: () => void;
  onDue?: () => void;
  onDelete: () => void;
  overlapWith?: string;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const due = describeDueAt(todo.due_at);
  const dueToneStyle =
    due?.tone === "overdue"
      ? s.dueOverdue
      : due?.tone === "today"
        ? s.dueToday
        : s.dueSoon;

  return (
    <View style={[s.todoRow, highlighted && s.todoRowHighlighted]}>
      <Pressable
        onPress={onToggle}
        hitSlop={10}
        style={s.checkbox}
        disabled={busy}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: todo.checked, disabled: busy }}
      >
        <Ionicons
          name={todo.checked ? "checkbox" : "square-outline"}
          size={22}
          color={todo.checked ? C.primary : C.textTertiary}
        />
      </Pressable>
      <View style={s.todoMain}>
        <Text
          style={[s.todoText, todo.checked && s.todoDone]}
          selectable
          numberOfLines={4}
        >
          {todo.content}
        </Text>
        {due && !todo.checked ? (
          <Text style={[s.dueLabel, dueToneStyle]}>{due.label}</Text>
        ) : null}
        {overlapWith && !todo.checked ? (
          <Text style={s.overlapLabel}>
            {t("todos.overlap_inline", { task: overlapWith })}
          </Text>
        ) : null}
      </View>
      {!todo.checked && onDue ? (
        <Pressable onPress={onDue} hitSlop={8} style={s.dueBtn}>
          <Ionicons
            name={todo.due_at ? "calendar" : "calendar-outline"}
            size={18}
            color={todo.due_at ? C.primary : C.textTertiary}
          />
        </Pressable>
      ) : null}
      <Pressable onPress={onDelete} hitSlop={8}>
        <Ionicons name="trash-outline" size={16} color={C.textTertiary} />
      </Pressable>
    </View>
  );
}
