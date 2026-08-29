import { useEffect, useMemo, useState } from "react";
import {
  Keyboard,
  Platform,
  Pressable,
  Text,
  TextInput,
  View,
} from "react-native";
import DateTimePicker, { type DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { SheetFormHeader } from "@/components/SheetFormHeader";
import { defaultDueDate } from "@/components/todos/todoHelpers";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import type { RecurrenceRule, Todo } from "@/lib/api";
import { describeDueAt, toDueAtIso } from "@/lib/todos/dueDate";
import { findOverlappingReminder } from "@/lib/todos/reminderOverlap";
import { RECURRENCE_RULES } from "@/lib/todos/recurrence";
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
  onSave: (content: string, dueDate: Date, recurrence: RecurrenceRule | null) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const [text, setText] = useState("");
  const [dueDate, setDueDate] = useState(() => defaultDueDate());
  const [repeat, setRepeat] = useState<RecurrenceRule | null>(null);
  const [showPicker, setShowPicker] = useState(Platform.OS === "ios");

  const overlap = useMemo(
    () => findOverlappingReminder(todos, dueDate),
    [todos, dueDate],
  );

  const reset = () => {
    setText("");
    setDueDate(defaultDueDate());
    setRepeat(null);
    setShowPicker(Platform.OS === "ios");
  };

  useEffect(() => {
    if (!visible) reset();
  }, [visible]);

  const canSave = text.trim().length > 0 && !saving;

  const handleClose = () => {
    if (saving) return;
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
    onSave(text, dueDate, repeat);
  };

  return (
    <AppSheet
      visible={visible}
      onClose={handleClose}
      variant="bottom"
      keyboardAvoiding
      withHandle={false}
      contentContainerStyle={[s.sheet, { paddingHorizontal: 0, paddingTop: 0 }]}
    >
      <SheetFormHeader
        title={t("todos.reminder_sheet_title")}
        onCancel={handleClose}
        onSave={handleSave}
        cancelLabel={t("common.cancel")}
        saveLabel={t("todos.save")}
        saving={saving}
        saveDisabled={text.trim().length === 0}
      />

      <View style={s.sheetBody}>
        <Text style={s.formLabel}>{t("todos.reminder_label")}</Text>
        <TextInput
          style={s.titleInput}
          placeholder={t("todos.reminder_placeholder")}
          placeholderTextColor={C.textDisabled}
          value={text}
          onChangeText={setText}
          autoFocus
          returnKeyType="done"
          maxLength={500}
          editable={!saving}
        />

        <Text style={[s.formLabel, s.fieldGap]}>{t("todos.due_date_required")}</Text>
        {Platform.OS === "ios" && showPicker ? (
          <DateTimePicker
            value={dueDate}
            mode="datetime"
            display="spinner"
            onChange={onPickerChange}
            disabled={saving}
          />
        ) : (
          <Pressable
            style={s.dateChip}
            onPress={() => {
              // Native Android calendar sits above our Modal; dismiss the
              // soft keyboard first so the sheet isn't trapped underneath.
              Keyboard.dismiss();
              setShowPicker(true);
            }}
            disabled={saving}
            accessibilityRole="button"
            accessibilityLabel={t("todos.due_date_required")}
          >
            <Icon name="calendar" size={18} color={C.primary} />
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
            disabled={saving}
          />
        ) : null}

        <Text style={[s.formLabel, s.fieldGap]}>{t("todos.repeat_label")}</Text>
        <View style={s.repeatRow}>
          <Pressable
            style={[s.repeatChip, repeat == null && s.repeatChipOn]}
            onPress={() => setRepeat(null)}
            disabled={saving}
            accessibilityRole="button"
            accessibilityState={{ selected: repeat == null }}
          >
            <Text style={[s.repeatChipText, repeat == null && s.repeatChipTextOn]}>
              {t("todos.repeat_none")}
            </Text>
          </Pressable>
          {RECURRENCE_RULES.map((rule) => {
            const on = repeat === rule;
            return (
              <Pressable
                key={rule}
                style={[s.repeatChip, on && s.repeatChipOn]}
                onPress={() => setRepeat(rule)}
                disabled={saving}
                accessibilityRole="button"
                accessibilityState={{ selected: on }}
              >
                <Text style={[s.repeatChipText, on && s.repeatChipTextOn]}>
                  {t(`todos.repeat_${rule}`)}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {overlap ? (
          <View style={s.overlapNote}>
            <Icon name="information-circle-outline" size={16} color={C.danger} />
            <Text style={s.overlapNoteText}>
              {t("todos.overlap_inline", { title: overlap.content })}
            </Text>
          </View>
        ) : null}
      </View>
    </AppSheet>
  );
}
