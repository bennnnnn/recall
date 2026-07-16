import { useMemo } from "react";
import { Modal, Platform, Pressable, Text, View } from "react-native";
import DateTimePicker, { type DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { makeTodosStyles } from "@/components/todos/todosStyles";
import type { Todo } from "@/lib/api";
import { findOverlappingReminder } from "@/lib/reminderOverlap";
import { useTheme } from "@/lib/theme";

export function DuePickerModal({
  todos,
  duePicker,
  onDismiss,
  onChange,
  onConfirm,
}: {
  todos: Todo[];
  duePicker: { todo: Todo; date: Date } | null;
  onDismiss: () => void;
  onChange: (event: DateTimePickerEvent, date?: Date) => void;
  onConfirm: () => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const insets = useSafeAreaInsets();
  if (!duePicker) return null;

  const overlap = findOverlappingReminder(todos, duePicker.date, {
    excludeId: duePicker.todo.id,
  });

  if (Platform.OS === "android") {
    return (
      <DateTimePicker
        value={duePicker.date}
        mode="datetime"
        onChange={onChange}
      />
    );
  }

  return (
    <Modal transparent animationType="slide" visible>
      <Pressable style={s.pickerBackdrop} onPress={onDismiss} />
      <View style={[s.pickerSheet, { paddingBottom: insets.bottom }]}>
        <View style={s.pickerHeader}>
          <Pressable onPress={onDismiss} hitSlop={8}>
            <Text style={s.pickerCancel}>{t("common.cancel")}</Text>
          </Pressable>
          <Text style={s.pickerTitle}>
            {duePicker.todo.due_at ? t("todos.change_due") : t("todos.set_due")}
          </Text>
          <Pressable onPress={onConfirm} hitSlop={8}>
            <Text style={s.pickerDone}>{t("todos.due_done")}</Text>
          </Pressable>
        </View>
        <DateTimePicker
          value={duePicker.date}
          mode="datetime"
          display="spinner"
          onChange={onChange}
        />
        {overlap ? (
          <View style={[s.overlapNote, s.pickerOverlapNote]}>
            <Ionicons name="information-circle-outline" size={16} color={C.danger} />
            <Text style={s.overlapNoteText}>
              {t("todos.overlap_inline", { title: overlap.content })}
            </Text>
          </View>
        ) : null}
      </View>
    </Modal>
  );
}
