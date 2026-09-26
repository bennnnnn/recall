import { useMemo } from "react";
import { Platform, StyleSheet, View } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";

import { SettingsPickerSheet } from "@/components/settings/SettingsPickerSheet";
import { SelectMenu } from "@/ui/overlay/SelectMenu";
import { ReminderDateTimePicker } from "@/features/todos/components/ReminderDateTimePicker";
import { repeatMessageKey } from "@/features/todos/model/repeatLabel";
import { TodoCategoryPicker } from "@/features/todos/components/TodoCategoryField";
import type { SchedulePanel } from "@/features/todos/components/TodoDateFields";
import { withCalendarDate, withClockTime } from "@/features/todos/model/dueDate";
import type { RecurrenceRule, Todo } from "@/lib/api";
import { RECURRENCE_RULES } from "@/lib/api/types";

export type TodoPicker = "category" | SchedulePanel;

const CLOCK_HEIGHT = 216;

/**
 * Category, repeat, date, and time use the Settings choice card.
 * Android date and time stay the system dialog, which is already its own window.
 */
export function TodoPickers({
  picker,
  topic,
  todos,
  dueDate,
  repeat,
  disabled,
  onTopic,
  onDueDate,
  onRepeat,
  onClose,
}: {
  picker: TodoPicker;
  topic: string;
  todos: Todo[];
  dueDate: Date | null;
  repeat: RecurrenceRule | null;
  disabled?: boolean;
  onTopic: (topic: string) => void;
  onDueDate: (date: Date) => void;
  onRepeat: (rule: RecurrenceRule | null) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const s = useMemo(() => StyleSheet.create({ clock: { height: CLOCK_HEIGHT } }), []);

  if (picker === "category") {
    return (
      <TodoCategoryPicker
        topic={topic}
        todos={todos}
        disabled={disabled}
        onChange={onTopic}
        onClose={onClose}
      />
    );
  }

  if (picker === "repeat") {
    const options = [
      { key: "none", label: t("todos.repeat_none") },
      ...RECURRENCE_RULES.map((rule) => ({ key: rule, label: t(repeatMessageKey(rule)) })),
    ];
    return (
      <SelectMenu
        visible
        options={options}
        selectedKey={repeat ?? "none"}
        disabled={disabled}
        onSelect={(key) => onRepeat(key === "none" ? null : (key as RecurrenceRule))}
        onClose={onClose}
      />
    );
  }

  if (!dueDate) return null;

  const onChange = (event: DateTimePickerEvent, date?: Date) => {
    if (event.type === "dismissed" || !date) {
      if (Platform.OS === "android") onClose();
      return;
    }
    onDueDate(picker === "date" ? withCalendarDate(dueDate, date) : withClockTime(dueDate, date));
    if (Platform.OS === "android") onClose();
  };
  const clock = (
    <ReminderDateTimePicker mode={picker} value={dueDate} disabled={disabled} onChange={onChange} />
  );
  if (Platform.OS === "android") return clock;

  return (
    <SettingsPickerSheet visible onClose={onClose}>
      <View style={s.clock}>{clock}</View>
    </SettingsPickerSheet>
  );
}
