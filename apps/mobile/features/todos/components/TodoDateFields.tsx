import { useMemo, useRef, useState, type Ref } from "react";
import { Keyboard, Pressable, Text, View, type HostInstance } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { SelectMenu } from "@/ui/overlay/SelectMenu";
import { repeatMessageKey } from "@/features/todos/model/repeatLabel";
import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import { dateOnly, type TodoDue } from "@/features/todos/model/dueDate";
import type { RecurrenceRule, Todo } from "@/lib/api";
import { isSameDay } from "@/lib/datetime/calendarGrid";
import { formatDate } from "@/lib/datetime/format";
import { findOverlappingReminder } from "@/features/todos/model/reminderOverlap";
import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  normalizeReminderLeadMinutes,
  REMINDER_LEAD_OPTIONS,
} from "@/features/todos/model/reminderTiming";
import type { RemindAt } from "@/features/todos/hooks/useRemindAt";
import { ensureNotificationPermission } from "@/features/todos/model/todoReminders";
import { IconSize } from "@/ui/icons/sizes";
import { useTheme } from "@/lib/theme";
import { alertDialog } from "@/ui/overlay/dialogs";
import { IconButton } from "@/ui/controls/IconButton";
import { ListRow } from "@/ui/list/ListRow";

export type SchedulePanel = "date" | "time" | "repeat";

const NO_REMINDER: RemindAt = { status: "none" };

/**
 * Date (with year), time, and repeat are separate rows. A to-do can stay undated, or have
 * a date alone ("—" for its time, and no Remind at); a time makes it a timed one, and the
 * remove button beside the time makes it a date alone again. The one beside the date makes
 * it undated: its time, reminder and repeat go with the date.
 */
export function TodoDateFields({
  due,
  onDueChange,
  repeat,
  onRepeatChange,
  todos,
  excludeId,
  remindAt = NO_REMINDER,
  disabled,
  review = false,
  leadMinutes,
  onChangeLead,
  onOpen,
}: {
  due: TodoDue | null;
  onDueChange: (due: TodoDue | null) => void;
  repeat: RecurrenceRule | null;
  onRepeatChange: (rule: RecurrenceRule | null) => void;
  todos: Todo[];
  excludeId?: string;
  /** When its reminder goes out, the server's (`useRemindAt`): Remind at on the detail page. */
  remindAt?: RemindAt;
  disabled?: boolean;
  /** Icon rows on the detail page, instead of labeled form fields. */
  review?: boolean;
  /** The profile's reminder lead, which the Remind at menu sets. */
  leadMinutes?: number;
  onChangeLead?: (minutes: number) => Promise<void>;
  onOpen: (panel: SchedulePanel) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const [remindOpen, setRemindOpen] = useState(false);
  const [savingLead, setSavingLead] = useState(false);
  const remindRowRef = useRef<HostInstance>(null);
  const lead = normalizeReminderLeadMinutes(leadMinutes ?? DEFAULT_REMINDER_LEAD_MINUTES);
  // The server's instant (the lead time, after quiet hours); "—" until it is known. Quiet
  // hours can move it to the next morning, and a lead before midnight to the evening before:
  // then it names its day.
  const remindAtLabel = remindAt.status !== "at"
    ? "—"
    : formatDate(remindAt.at, due && isSameDay(remindAt.at, due.date) ? "time" : "weekdayTime");
  const leadLabel = t("settings.reminder_lead_value", { count: lead });

  // Only a time can share its slot with another reminder.
  const overlap = useMemo(
    () =>
      due?.hasTime
        ? findOverlappingReminder(todos, due.date, excludeId ? { excludeId } : undefined)
        : null,
    [todos, due, excludeId],
  );
  const repeatLabel = t(repeatMessageKey(repeat));
  const dateLabel = due ? formatDate(due.date, "monthDayYear") : t("todos.add_date");
  const timeLabel = due?.hasTime ? formatDate(due.date, "time") : "—";

  // Opening a picker changes nothing; a time, which brings a reminder, asks for alerts first.
  const openPanel = (panel: SchedulePanel) => {
    Keyboard.dismiss();
    if (panel === "time" && !due?.hasTime) void ensureNotificationPermission().catch(() => undefined);
    onOpen(panel);
  };

  // A repeat needs a date: it goes with it.
  const removeDate = () => { onDueChange(null); onRepeatChange(null); };
  // The day and repeat stay: a date alone, with no reminder.
  const removeTime = due?.hasTime ? () => onDueChange(dateOnly(due.date)) : undefined;

  if (review) {
    return (
      <>
      <View style={s.reviewList}>
        <ReviewRow
          icon="calendar"
          label={t("todos.date_label")}
          value={dateLabel}
          disabled={disabled}
          onPress={() => openPanel("date")}
          accessibilityLabel={due ? t("todos.change_due") : t("todos.add_date")}
          onRemove={due ? removeDate : undefined}
          removeLabel={t("todos.remove_date")}
        />
        <ReviewRow
          icon="clock"
          label={t("todos.time_label")}
          value={timeLabel}
          disabled={disabled}
          onPress={() => openPanel("time")}
          accessibilityLabel={t("todos.time_label")}
          onRemove={removeTime}
          removeLabel={t("todos.remove_time")}
        />
        {due && remindAt.status !== "none" ? (
          <ReviewRow
            ref={remindRowRef}
            icon="bell"
            label={t("todos.remind_at")}
            value={remindAtLabel}
            disabled={disabled || savingLead}
            onPress={() => {
              Keyboard.dismiss();
              setRemindOpen(true);
            }}
            accessibilityLabel={remindAt.status === "at"
              ? `${t("todos.remind_at")}, ${remindAtLabel}, ${leadLabel}`
              : `${t("todos.remind_at")}, ${leadLabel}`}
          />
        ) : null}
        <ReviewRow
          icon="repeat"
          label={t("todos.repeat_label")}
          value={repeatLabel}
          disabled={disabled}
          onPress={() => openPanel("repeat")}
          accessibilityLabel={`${t("todos.repeat_label")}, ${repeatLabel}`}
        />
        {overlap ? (
          <View style={s.overlapNote}>
            <Icon name="info" size={IconSize.xs} color={C.danger} />
            <Text style={s.overlapNoteText}>
              {t("todos.overlap_inline", { title: overlap.content })}
            </Text>
          </View>
        ) : null}
      </View>
      <SelectMenu
        visible={remindOpen}
        anchorRef={remindRowRef}
        options={REMINDER_LEAD_OPTIONS.map((minutes) => ({
          key: String(minutes),
          label: t("settings.reminder_lead_value", { count: minutes }),
        }))}
        selectedKey={String(lead)}
        disabled={disabled || savingLead}
        onSelect={(key) => {
          const minutes = normalizeReminderLeadMinutes(Number(key));
          if (!onChangeLead || minutes === lead) return;
          setSavingLead(true);
          void onChangeLead(minutes)
            .catch(() => { void alertDialog({ title: t("common.error") }); })
            .finally(() => setSavingLead(false));
        }}
        onClose={() => setRemindOpen(false)}
      />
      </>
    );
  }

  return (
    <>
      <Text style={[s.formLabel, s.fieldGap]}>{t("todos.date_label")}</Text>
      <View style={s.dateRow}>
        <Pressable
          style={[s.repeatField, s.fieldGrow]}
          onPress={() => openPanel("date")}
          disabled={disabled}
          accessibilityRole="button"
          accessibilityLabel={due ? t("todos.change_due") : t("todos.add_date")}
        >
          <Icon name="calendar" size={IconSize.sm} color={C.primary} />
          <Text style={s.repeatFieldText}>{dateLabel}</Text>
        </Pressable>
        {due ? <RemoveButton label={t("todos.remove_date")} disabled={disabled} onPress={removeDate} /> : null}
      </View>

      <Text style={[s.formLabel, s.fieldGap]}>{t("todos.time_label")}</Text>
      <View style={s.dateRow}>
        <Pressable
          style={[s.repeatField, s.fieldGrow]}
          onPress={() => openPanel("time")}
          disabled={disabled}
          accessibilityRole="button"
          accessibilityLabel={t("todos.time_label")}
        >
          <Icon name="clock" size={IconSize.sm} color={C.primary} />
          <Text style={s.repeatFieldText}>{timeLabel}</Text>
        </Pressable>
        {removeTime ? <RemoveButton label={t("todos.remove_time")} disabled={disabled} onPress={removeTime} /> : null}
      </View>

      <Text style={[s.formLabel, s.fieldGap]}>{t("todos.repeat_label")}</Text>
      <Pressable
        style={s.repeatField}
        onPress={() => openPanel("repeat")}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel={`${t("todos.repeat_label")}, ${repeatLabel}`}
      >
        <Text style={s.repeatFieldText}>{repeatLabel}</Text>
        <Icon name="chevron-right" size={IconSize.sm} color={C.textTertiary} />
      </Pressable>

      {overlap ? (
        <View style={s.overlapNote}>
          <Icon name="info" size={IconSize.xs} color={C.danger} />
          <Text style={s.overlapNoteText}>
            {t("todos.overlap_inline", { title: overlap.content })}
          </Text>
        </View>
      ) : null}
    </>
  );
}

/** The circled x beside a field, which takes its value off. */
function RemoveButton({ label, disabled, onPress }: {
  label: string;
  disabled?: boolean;
  onPress: () => void;
}) {
  const C = useTheme();
  return (
    <IconButton
      name="close-circle"
      size={IconSize.md}
      color={C.textTertiary}
      disabled={disabled}
      onPress={onPress}
      accessibilityLabel={label}
    />
  );
}

function ReviewRow({
  icon,
  label,
  value,
  disabled,
  inset = false,
  onPress,
  accessibilityLabel,
  onRemove,
  removeLabel = "",
  ref,
}: {
  icon?: "calendar" | "clock" | "bell" | "repeat";
  label: string;
  value: string;
  disabled?: boolean;
  inset?: boolean;
  onPress: () => void;
  accessibilityLabel: string;
  /** A remove button beside the row, not in it: inside, a screen reader would not reach it. */
  onRemove?: () => void;
  removeLabel?: string;
  ref?: Ref<HostInstance>;
}) {
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const row = (
    <ListRow
      ref={ref}
      appearance="plain"
      icon={icon}
      iconColor={C.textSecondary}
      title={label}
      detail={value}
      detailStyle="pill"
      inset={inset}
      disabled={disabled}
      onPress={onPress}
      accessibilityLabel={accessibilityLabel}
      style={onRemove ? s.fieldGrow : undefined}
    />
  );
  if (!onRemove) return row;
  return (
    <View style={s.dateRow}>
      {row}
      <RemoveButton label={removeLabel} disabled={disabled} onPress={onRemove} />
    </View>
  );
}
