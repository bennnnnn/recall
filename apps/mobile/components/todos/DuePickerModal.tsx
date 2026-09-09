import { useEffect, useMemo, useState } from "react";
import { Keyboard, Platform, Pressable, Text, View } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { ReminderDateTimePicker } from "@/components/todos/ReminderDateTimePicker";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { SheetFormHeader } from "@/components/SheetFormHeader";
import {
  RepeatPickerSheet,
  repeatMessageKey,
} from "@/components/todos/RepeatPickerSheet";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import type { RecurrenceRule, Todo } from "@/lib/api";
import { describeDueAt, toDueAtIso } from "@/lib/todos/dueDate";
import { findOverlappingReminder } from "@/lib/todos/reminderOverlap";
import { useTheme } from "@/lib/theme";

export type DuePickerState = {
  todo: Todo;
  date: Date;
  recurrence: RecurrenceRule | null;
};

export function DuePickerModal({
  todos,
  duePicker,
  saving = false,
  onDismiss,
  onChange,
  onConfirm,
  onRecurrenceChange,
}: {
  todos: Todo[];
  duePicker: DuePickerState | null;
  saving?: boolean;
  onDismiss: () => void;
  onChange: (event: DateTimePickerEvent, date?: Date) => void;
  onConfirm: () => void;
  onRecurrenceChange: (rule: RecurrenceRule | null) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const [showPicker, setShowPicker] = useState(Platform.OS === "ios");
  const [repeatPickerOpen, setRepeatPickerOpen] = useState(false);

  useEffect(() => {
    setShowPicker(Platform.OS === "ios");
    setRepeatPickerOpen(false);
  }, [duePicker?.todo.id]);

  if (!duePicker) return null;

  const overlap = findOverlappingReminder(todos, duePicker.date, {
    excludeId: duePicker.todo.id,
  });
  const repeatLabel = t(repeatMessageKey(duePicker.recurrence));

  const onPickerChange = (event: DateTimePickerEvent, date?: Date) => {
    if (Platform.OS === "android") {
      setShowPicker(false);
      if (event.type === "dismissed" || !date) return;
      onChange(event, date);
      return;
    }
    onChange(event, date);
  };

  return (
    <AppSheet
      visible
      onClose={() => {
        if (!saving) onDismiss();
      }}
      variant="bottom"
      withHandle={false}
      minBottomPadding={24}
      contentContainerStyle={s.pickerSheet}
    >
      <SheetFormHeader
        title={duePicker.todo.due_at ? t("todos.change_due") : t("todos.set_due")}
        onCancel={onDismiss}
        onSave={onConfirm}
        cancelLabel={t("common.cancel")}
        saveLabel={t("todos.due_done")}
        saving={saving}
      />
      <View style={s.sheetBody}>
        <Text style={s.formLabel}>{t("todos.due_date_required")}</Text>
        {Platform.OS === "ios" && showPicker ? (
          <ReminderDateTimePicker
            key={duePicker.todo.id}
            value={duePicker.date}
            onChange={onPickerChange}
            disabled={saving}
          />
        ) : (
          <Pressable
            style={s.dateChip}
            onPress={() => {
              Keyboard.dismiss();
              setShowPicker(true);
            }}
            disabled={saving}
            accessibilityRole="button"
            accessibilityLabel={t("todos.due_date_required")}
          >
            <Icon name="calendar" size={18} color={C.primary} />
            <Text style={s.dateChipText}>
              {describeDueAt(toDueAtIso(duePicker.date))?.label ?? ""}
            </Text>
          </Pressable>
        )}
        {Platform.OS === "android" && showPicker ? (
          <ReminderDateTimePicker
            key={duePicker.todo.id}
            value={duePicker.date}
            onChange={onPickerChange}
            disabled={saving}
          />
        ) : null}

        <Text style={[s.formLabel, s.fieldGap]}>{t("todos.repeat_label")}</Text>
        <View>
          <Pressable
            style={[s.repeatField, repeatPickerOpen && s.repeatFieldOpen]}
            onPress={() => {
              Keyboard.dismiss();
              setRepeatPickerOpen((open) => !open);
            }}
            disabled={saving}
            accessibilityRole="button"
            accessibilityState={{ expanded: repeatPickerOpen }}
            accessibilityLabel={`${t("todos.repeat_label")}, ${repeatLabel}`}
          >
            <Text style={s.repeatFieldText}>{repeatLabel}</Text>
            <Icon
              name={repeatPickerOpen ? "chevron-up" : "chevron-down"}
              size={18}
              color={C.textTertiary}
            />
          </Pressable>
          {repeatPickerOpen ? (
            <RepeatPickerSheet
              selected={duePicker.recurrence}
              onSelect={(rule) => {
                onRecurrenceChange(rule);
                setRepeatPickerOpen(false);
              }}
            />
          ) : null}
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
