import { useEffect, useMemo, useState } from "react";
import { Keyboard, Platform, Pressable, Text, View } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { ReminderDateTimePicker } from "@/components/todos/ReminderDateTimePicker";
import {
  RepeatPickerSheet,
  repeatMessageKey,
} from "@/components/todos/RepeatPickerSheet";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import type { RecurrenceRule, Todo } from "@/lib/api";
import { describeDueAt, toDueAtIso } from "@/lib/todos/dueDate";
import { findOverlappingReminder } from "@/lib/todos/reminderOverlap";
import { useTheme } from "@/lib/theme";

/**
 * Shared due-date + repeat fields for reminder add/edit sheets. The date
 * starts as a chip on every platform (the iOS spinner expands on tap) so the
 * sheet opens at the same density as Android instead of half spinner.
 */
export function ReminderScheduleFields({
  dueDate,
  onDueDateChange,
  repeat,
  onRepeatChange,
  todos,
  excludeId,
  disabled,
}: {
  dueDate: Date;
  onDueDateChange: (date: Date) => void;
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
    () => findOverlappingReminder(todos, dueDate, excludeId ? { excludeId } : undefined),
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

  return (
    <>
      <Text style={[s.formLabel, s.fieldGap]}>{t("todos.due_date_required")}</Text>
      {showPicker ? (
        <ReminderDateTimePicker
          value={dueDate}
          onChange={onPickerChange}
          disabled={disabled}
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
          disabled={disabled}
          accessibilityRole="button"
          accessibilityLabel={t("todos.due_date_required")}
        >
          <Icon name="calendar" size={18} color={C.primary} />
          <Text style={s.dateChipText}>
            {describeDueAt(toDueAtIso(dueDate))?.label ?? ""}
          </Text>
        </Pressable>
      )}

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
