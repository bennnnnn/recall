import { useMemo, useRef, useState, type Ref } from "react";
import { Keyboard, Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { SelectMenu } from "@/ui/overlay/SelectMenu";
import { repeatMessageKey } from "@/features/todos/model/repeatLabel";
import { makeTodosStyles } from "@/features/todos/components/todosStyles";
import { defaultDueDate } from "@/features/todos/components/todoHelpers";
import type { RecurrenceRule, Todo } from "@/lib/api";
import { formatClockTime, formatMonthDayYear } from "@/lib/datetime/format";
import { findOverlappingReminder } from "@/features/todos/model/reminderOverlap";
import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  normalizeReminderLeadMinutes,
  REMINDER_LEAD_OPTIONS,
  remindAtDate,
} from "@/features/todos/model/reminderTiming";
import { ensureNotificationPermission } from "@/features/todos/model/todoReminders";
import { IconSize } from "@/ui/icons/sizes";
import { useTheme } from "@/lib/theme";
import { alertDialog } from "@/ui/overlay/dialogs";
import { ListRow } from "@/ui/list/ListRow";

export type SchedulePanel = "date" | "time" | "repeat";

/**
 * Date (with year), time, and repeat are separate rows.
 * A to-do can stay undated until the date row is opened.
 */
export function TodoDateFields({
  dueDate,
  onDueDateChange,
  repeat,
  onRepeatChange,
  todos,
  excludeId,
  disabled,
  review = false,
  leadMinutes,
  onChangeLead,
  onOpen,
}: {
  dueDate: Date | null;
  onDueDateChange: (date: Date | null) => void;
  repeat: RecurrenceRule | null;
  onRepeatChange: (rule: RecurrenceRule | null) => void;
  todos: Todo[];
  excludeId?: string;
  disabled?: boolean;
  /** Icon rows on the detail page, instead of labeled form fields. */
  review?: boolean;
  /** Account to-do alert from Settings. */
  leadMinutes?: number;
  onChangeLead?: (minutes: number) => Promise<void>;
  onOpen: (panel: SchedulePanel) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const [remindOpen, setRemindOpen] = useState(false);
  const [savingLead, setSavingLead] = useState(false);
  const remindRowRef = useRef<View>(null);
  const lead = normalizeReminderLeadMinutes(leadMinutes ?? DEFAULT_REMINDER_LEAD_MINUTES);
  const remindAt = dueDate ? remindAtDate(dueDate, lead) : null;

  const overlap = useMemo(
    () =>
      dueDate
        ? findOverlappingReminder(todos, dueDate, excludeId ? { excludeId } : undefined)
        : null,
    [todos, dueDate, excludeId],
  );
  const repeatLabel = t(repeatMessageKey(repeat));
  const dateLabel = dueDate ? formatMonthDayYear(dueDate) : t("todos.add_date");
  const timeLabel = dueDate ? formatClockTime(dueDate) : "—";

  const openPanel = (panel: SchedulePanel) => {
    Keyboard.dismiss();
    if (!dueDate) {
      onDueDateChange(defaultDueDate());
      onRepeatChange(null);
      void ensureNotificationPermission().catch(() => undefined);
    }
    onOpen(panel);
  };

  const removeDate = () => {
    onDueDateChange(null);
    onRepeatChange(null);
  };

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
          accessibilityLabel={dueDate ? t("todos.change_due") : t("todos.add_date")}
        />
        <ReviewRow
          icon="clock"
          label={t("todos.time_label")}
          value={timeLabel}
          disabled={disabled}
          onPress={() => openPanel("time")}
          accessibilityLabel={t("todos.time_label")}
        />
        {remindAt ? (
          <ReviewRow
            ref={remindRowRef}
            icon="bell"
            label={t("todos.remind_at")}
            value={formatClockTime(remindAt)}
            disabled={disabled || savingLead}
            onPress={() => {
              Keyboard.dismiss();
              setRemindOpen(true);
            }}
            accessibilityLabel={`${t("todos.remind_at")}, ${formatClockTime(remindAt)}, ${t("settings.reminder_lead_value", { count: lead })}`}
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
          accessibilityLabel={dueDate ? t("todos.change_due") : t("todos.add_date")}
        >
          <Icon name="calendar" size={IconSize.sm} color={C.primary} />
          <Text style={s.repeatFieldText}>{dateLabel}</Text>
        </Pressable>
        {dueDate ? (
          <Pressable
            style={s.removeDateButton}
            onPress={removeDate}
            disabled={disabled}
            accessibilityRole="button"
            accessibilityLabel={t("todos.remove_date")}
          >
            <Icon name="close-circle" size={IconSize.md} color={C.textTertiary} />
          </Pressable>
        ) : null}
      </View>

      <Text style={[s.formLabel, s.fieldGap]}>{t("todos.time_label")}</Text>
      <Pressable
        style={s.repeatField}
        onPress={() => openPanel("time")}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel={t("todos.time_label")}
      >
        <Icon name="clock" size={IconSize.sm} color={C.primary} />
        <Text style={s.repeatFieldText}>{timeLabel}</Text>
      </Pressable>

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

function ReviewRow({
  icon,
  label,
  value,
  disabled,
  inset = false,
  onPress,
  accessibilityLabel,
  ref,
}: {
  icon?: "calendar" | "clock" | "bell" | "repeat";
  label: string;
  value: string;
  disabled?: boolean;
  inset?: boolean;
  onPress: () => void;
  accessibilityLabel: string;
  ref?: Ref<View>;
}) {
  const C = useTheme();
  return (
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
    />
  );
}
