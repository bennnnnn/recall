import { useState } from "react";
import { useTranslation } from "react-i18next";

import { SelectMenu } from "@/ui/overlay/SelectMenu";
import { DatePickerDialog } from "@/ui/pickers/DatePickerDialog";
import { TimePickerDialog } from "@/ui/pickers/TimePickerDialog";
import { repeatMessageKey } from "@/features/todos/model/repeatLabel";
import { TodoCategoryPicker } from "@/features/todos/components/TodoCategoryField";
import type { SchedulePanel } from "@/features/todos/components/TodoDateFields";
import { dateOnly, defaultDueDate, withCalendarDate, type TodoDue } from "@/features/todos/model/dueDate";
import type { RecurrenceRule, Todo } from "@/lib/api";
import { RECURRENCE_RULES } from "@/lib/api/types";
import { timeFromDate, withTimeOfDay } from "@/lib/datetime/clockDial";
import { useLatestRef } from "@/lib/latestRef";

export type TodoPicker = "category" | SchedulePanel;

/**
 * The editor's pickers: category sheet, repeat popover, and the app's date
 * and clock dialogs. They stay mounted so each one can fade out; `picker`
 * says which is open. A date or time from an earlier opening (another to-do,
 * or a dialog left over while saving) is dropped. Opening one changes nothing:
 * the to-do changes on OK. A date picked alone has no time; a time makes the
 * to-do a timed one, with its reminder.
 */
export function TodoPickers({
  picker,
  topic,
  todos,
  due,
  repeat,
  disabled,
  onTopic,
  onDue,
  onRepeat,
  onClose,
}: {
  picker: TodoPicker | null;
  topic: string;
  todos: Todo[];
  due: TodoDue | null;
  repeat: RecurrenceRule | null;
  disabled?: boolean;
  onTopic: (topic: string) => void;
  onDue: (due: TodoDue) => void;
  onRepeat: (rule: RecurrenceRule | null) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  // An undated to-do's date dialog starts at today; the clock starts at the to-do's time,
  // or with none at the suggested one (9:00, or the next hour).
  const clock = due?.hasTime ? due.date : defaultDueDate();
  // Each opening is counted, so a dialog from an older one can tell it is not the current one.
  const [opened, setOpened] = useState({ picker: null as TodoPicker | null, count: 0 });
  const openedCount = picker === opened.picker ? opened.count : opened.count + (picker ? 1 : 0);
  if (picker !== opened.picker) setOpened({ picker, count: openedCount });
  const latestOpened = useLatestRef(openedCount);
  const disabledRef = useLatestRef(disabled);
  const apply = (next: TodoDue) => {
    // An older opening leaves whatever is open now alone.
    if (latestOpened.current !== openedCount) return;
    if (!disabledRef.current) onDue(next);
    onClose();
  };

  return (
    <>
      {picker === "category" ? (
        <TodoCategoryPicker
          topic={topic}
          todos={todos}
          disabled={disabled}
          onChange={onTopic}
          onClose={onClose}
        />
      ) : null}
      <SelectMenu
        visible={picker === "repeat"}
        options={[
          { key: "none", label: t("todos.repeat_none") },
          ...RECURRENCE_RULES.map((rule) => ({ key: rule, label: t(repeatMessageKey(rule)) })),
        ]}
        selectedKey={repeat ?? "none"}
        disabled={disabled}
        onSelect={(key) => {
          // A repeat needs a date: an undated to-do's is today, with no time.
          if (key !== "none" && !due) onDue(dateOnly(new Date()));
          onRepeat(key === "none" ? null : (key as RecurrenceRule));
        }}
        onClose={onClose}
      />
      <DatePickerDialog
        visible={picker === "date"}
        value={due?.date ?? new Date()}
        // A time stays with its new day; a date alone stays one.
        onConfirm={(date) => apply(due?.hasTime ? { date: withCalendarDate(due.date, date), hasTime: true } : dateOnly(date))}
        onCancel={onClose}
      />
      <TimePickerDialog
        visible={picker === "time"}
        value={timeFromDate(clock)}
        // On its own day, or for an undated to-do the suggested time's.
        onConfirm={(time) => apply({ date: withTimeOfDay(due?.date ?? clock, time), hasTime: true })}
        onCancel={onClose}
      />
    </>
  );
}
