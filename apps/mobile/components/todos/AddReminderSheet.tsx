import { useEffect, useMemo, useState } from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  Text,
  TextInput,
  View,
} from "react-native";
import DateTimePicker, { type DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { defaultDueDate } from "@/components/todos/todoHelpers";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import type { Todo } from "@/lib/api";
import { describeDueAt, toDueAtIso } from "@/lib/dueDate";
import { findOverlappingReminder } from "@/lib/reminderOverlap";
import { useTheme } from "@/lib/theme";

export function AddReminderSheet({
  visible,
  saving,
  todos,
  onClose,
  onSave,
}: {
  visible: boolean;
  saving: boolean;
  todos: Todo[];
  onClose: () => void;
  onSave: (content: string, dueDate: Date) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const insets = useSafeAreaInsets();
  const [text, setText] = useState("");
  const [dueDate, setDueDate] = useState(() => defaultDueDate());
  const [showPicker, setShowPicker] = useState(Platform.OS === "ios");

  const overlap = useMemo(
    () => findOverlappingReminder(todos, dueDate),
    [todos, dueDate],
  );

  const reset = () => {
    setText("");
    setDueDate(defaultDueDate());
    setShowPicker(Platform.OS === "ios");
  };

  useEffect(() => {
    if (!visible) reset();
  }, [visible]);

  const canSave = text.trim().length > 0 && !saving;

  const handleClose = () => {
    onClose();
  };

  const onPickerChange = (event: DateTimePickerEvent, date?: Date) => {
    if (Platform.OS === "android") {
      setShowPicker(false);
      if (event.type === "dismissed" || !date) return;
      setDueDate(date);
      return;
    }
    if (date) setDueDate(date);
  };

  const handleSave = () => {
    if (!canSave) return;
    onSave(text, dueDate);
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={handleClose}>
      <KeyboardAvoidingView
        style={s.sheetOverlay}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <Pressable style={s.sheetBackdrop} onPress={handleClose} />
        <View style={[s.sheet, { paddingBottom: insets.bottom }]}>
        <View style={s.sheetHeader}>
          <Pressable onPress={handleClose} hitSlop={8}>
            <Text style={s.sheetCancel}>{t("common.cancel")}</Text>
          </Pressable>
          <Text style={s.sheetTitle}>{t("todos.reminder_sheet_title")}</Text>
          <Pressable onPress={handleSave} hitSlop={8} disabled={!canSave}>
            <Text style={[s.sheetSave, !canSave && s.sheetSaveDisabled]}>
              {t("todos.save")}
            </Text>
          </Pressable>
        </View>

        <View style={s.sheetBody}>
          <Text style={s.formLabel}>{t("todos.reminder_label")}</Text>
          <TextInput
            style={s.titleInput}
            placeholder={t("todos.reminder_placeholder")}
            placeholderTextColor={C.textTertiary}
            value={text}
            onChangeText={setText}
            autoFocus
            returnKeyType="done"
            maxLength={500}
          />

          <Text style={[s.formLabel, s.fieldGap]}>{t("todos.due_date_required")}</Text>
          {Platform.OS === "ios" && showPicker ? (
            <DateTimePicker
              value={dueDate}
              mode="datetime"
              display="spinner"
              onChange={onPickerChange}
            />
          ) : (
            <Pressable
              style={s.dateChip}
              onPress={() => {
                if (Platform.OS === "android") setShowPicker(true);
                else setShowPicker(true);
              }}
            >
              <Ionicons name="calendar" size={18} color={C.primary} />
              <Text style={s.dateChipText}>
                {describeDueAt(toDueAtIso(dueDate))?.label ?? ""}
              </Text>
            </Pressable>
          )}
          {Platform.OS === "android" && showPicker ? (
            <DateTimePicker
              value={dueDate}
              mode="datetime"
              onChange={onPickerChange}
            />
          ) : null}

          {overlap ? (
            <View style={s.overlapNote}>
              <Ionicons name="information-circle-outline" size={16} color={C.danger} />
              <Text style={s.overlapNoteText}>
                {t("todos.overlap_inline", { title: overlap.content })}
              </Text>
            </View>
          ) : null}
        </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}
