import { useMemo } from "react";
import { Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import Swipeable from "react-native-gesture-handler/ReanimatedSwipeable";
import { useTranslation } from "react-i18next";

import { makeTodosStyles } from "@/components/todos/todosStyles";
import type { Todo } from "@/lib/api";
import { describeDueAt } from "@/lib/dueDate";
import { notifyWarning } from "@/lib/haptics";
import { useTheme } from "@/lib/theme";

export function TodoRow({
  todo,
  variant,
  busy,
  highlighted,
  projectTitle,
  onToggle,
  onDue,
  onLinkProject,
  onDelete,
  overlapWith,
}: {
  todo: Todo;
  variant?: "open" | "done";
  busy?: boolean;
  highlighted?: boolean;
  projectTitle?: string | null;
  onToggle: () => void;
  onDue?: () => void;
  onLinkProject?: () => void;
  onDelete: () => void;
  overlapWith?: string;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const rowVariant = variant ?? (todo.checked ? "done" : "open");
  const due = describeDueAt(todo.due_at);
  const dueToneStyle =
    due?.tone === "overdue"
      ? s.dueOverdue
      : due?.tone === "today"
        ? s.dueToday
        : s.dueSoon;
  const handleDelete = () => {
    notifyWarning();
    onDelete();
  };

  const row = (
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
        {projectTitle ? (
          <Text style={s.projectLinked} numberOfLines={1}>
            {t("todos.project_linked", { title: projectTitle })}
          </Text>
        ) : null}
        {due && !todo.checked ? (
          <Text style={[s.dueLabel, dueToneStyle]}>{due.label}</Text>
        ) : null}
        {overlapWith && !todo.checked ? (
          <Text style={s.overlapLabel}>
            {t("todos.overlap_inline", { title: overlapWith })}
          </Text>
        ) : null}
      </View>
      {rowVariant === "open" && !todo.checked && onLinkProject ? (
        <Pressable
          onPress={onLinkProject}
          hitSlop={8}
          style={s.dueBtn}
          accessibilityLabel={t("todos.link_project")}
        >
          <Ionicons
            name={todo.project_id ? "folder" : "folder-outline"}
            size={18}
            color={todo.project_id ? C.primary : C.textTertiary}
          />
        </Pressable>
      ) : null}
      {rowVariant === "open" && !todo.checked && onDue ? (
        <Pressable
          onPress={onDue}
          hitSlop={8}
          style={s.dueBtn}
          accessibilityRole="button"
          accessibilityLabel={t("todos.due_date_a11y")}
        >
          <Ionicons
            name={todo.due_at ? "calendar" : "calendar-outline"}
            size={18}
            color={todo.due_at ? C.primary : C.textTertiary}
          />
        </Pressable>
      ) : null}
      {rowVariant === "done" ? (
        <Pressable
          onPress={handleDelete}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={t("common.delete")}
        >
          <Ionicons name="trash-outline" size={16} color={C.textTertiary} />
        </Pressable>
      ) : null}
    </View>
  );

  if (rowVariant !== "open") {
    return row;
  }

  return (
    <Swipeable
      friction={2}
      rightThreshold={40}
      overshootRight={false}
      containerStyle={s.swipeContainer}
      renderRightActions={() => (
        <Pressable
          style={s.swipeDeleteAction}
          onPress={handleDelete}
          accessibilityRole="button"
          accessibilityLabel={t("common.delete")}
        >
          <Ionicons name="trash-outline" size={18} color={C.onPrimary} />
          <Text style={s.swipeDeleteText}>{t("common.delete")}</Text>
        </Pressable>
      )}
    >
      {row}
    </Swipeable>
  );
}
