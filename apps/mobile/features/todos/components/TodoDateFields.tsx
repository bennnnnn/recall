import { useEffect, useMemo, useState } from "react";
import { Keyboard, Platform, Pressable, Text, View } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { ReminderDateTimePicker } from "@/features/todos/components/ReminderDateTimePicker";
import {
  RepeatPickerSheet,
  repeatMessageKey,
} from "@/features/todos/components/RepeatPickerSheet";
import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import type { RecurrenceRule, Todo } from "@/lib/api";
import { describeDueAt, toDueAtIso } from "@/features/todos/model/dueDate";
import { findOverlappingReminder } from "@/features/todos/model/reminderOverlap";
import { ensureNotificationPermission } from "@/features/todos/model/todoReminders";
import { useTheme } from "@/lib/theme";
import { defaultDueDate } from "@/features/todos/components/todoHelpers";

/**
 * Optional due-date + repeat fields for a to-do. Plain to-dos stay plain
 * unless the user explicitly adds a date.
 */
export function TodoDateFields({
  dueDate,
  onDueDateChange,
  repeat,
  onRepeatChange,
  todos,
  excludeId,
  disabled,
}: {
  dueDate: Date | null;
  onDueDateChange: (date: Date | null) => void;
  repeat: RecurrenceRule | null;
  onRepeatChange: (rule: RecurrenceRule | null) => void;
  todos: Todo[];
  excludeId?: string;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const [showPicker, setShowPicker] = useState(false);
  const [repeatPickerOpen, setRepeatPickerOpen] = useState(false);

  // A new edit target (or reopening) collapses both expansions.
  useEffect(() => {
    setShowPicker(false);
    setRepeatPickerOpen(false);
  }, [excludeId]);

  const overlap = useMemo(
    () => dueDate
      ? findOverlappingReminder(todos, dueDate, excludeId ? { excludeId } : undefined)
      : null,
    [todos, dueDate, excludeId],
  );
  const repeatLabel = t(repeatMessageKey(repeat));

  const onPickerChange = (event: DateTimePickerEvent, date?: Date) => {
    if (Platform.OS === "android") {
      setShowPicker(false);
      if (event.type === "dismissed" || !date) return;
      onDueDateChange(date);
      return;
    }
    if (date) onDueDateChange(date);
  };

  const addDate = () => {
    Keyboard.dismiss();
    onDueDateChange(defaultDueDate());
    onRepeatChange(null);
    setShowPicker(true);
    // Choosing a date is the explicit action that may lead to a reminder.
    void ensureNotificationPermission().catch(() => undefined);
  };

  const removeDate = () => {
    setShowPicker(false);
    setRepeatPickerOpen(false);
    onDueDateChange(null);
    onRepeatChange(null);
  };

  return (
    <>
      <Text style={[s.formLabel, s.fieldGap]}>{t("todos.date_optional")}</Text>
      {!dueDate ? (
        <Pressable
          style={s.dateChip}
          onPress={addDate}
          disabled={disabled}
          accessibilityRole="button"
          accessibilityLabel={t("todos.add_date")}
        >
          <Icon name="calendar-outline" size={18} color={C.primary} />
          <Text style={s.dateChipText}>{t("todos.add_date")}</Text>
        </Pressable>
      ) : showPicker ? (
        <ReminderDateTimePicker
          value={dueDate}
          onChange={onPickerChange}
          disabled={disabled}
        />
      ) : (
        <View style={s.dateRow}>
          <Pressable
            style={s.dateChip}
            onPress={() => {
              Keyboard.dismiss();
              setShowPicker(true);
            }}
            disabled={disabled}
            accessibilityRole="button"
            accessibilityLabel={t("todos.change_due")}
          >
            <Icon name="calendar" size={18} color={C.primary} />
            <Text style={s.dateChipText}>
              {describeDueAt(toDueAtIso(dueDate))?.label ?? ""}
            </Text>
          </Pressable>
          <Pressable
            style={s.removeDateButton}
            onPress={removeDate}
            disabled={disabled}
            accessibilityRole="button"
            accessibilityLabel={t("todos.remove_date")}
          >
            <Icon name="close-circle" size={22} color={C.textTertiary} />
          </Pressable>
        </View>
      )}

      {dueDate ? (
        <>
          <Text style={[s.formLabel, s.fieldGap]}>{t("todos.repeat_label")}</Text>
          <View>
            <Pressable
              style={[s.repeatField, repeatPickerOpen && s.repeatFieldOpen]}
              onPress={() => {
                Keyboard.dismiss();
                setRepeatPickerOpen((open) => !open);
              }}
              disabled={disabled}
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
                selected={repeat}
                onSelect={(rule) => {
                  onRepeatChange(rule);
                  setRepeatPickerOpen(false);
                }}
              />
            ) : null}
          </View>
        </>
      ) : null}

      {overlap ? (
        <View style={s.overlapNote}>
          <Icon name="information-circle-outline" size={16} color={C.danger} />
          <Text style={s.overlapNoteText}>
            {t("todos.overlap_inline", { title: overlap.content })}
          </Text>
        </View>
      ) : null}
    </>
  );
}
