import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";
import type { GoogleCalendarEvent, SuggestedReminder, Todo } from "@/lib/api";
import {
  addMonths,
  buildMonthCells,
  countCalendarEventsByDay,
  countRemindersByDay,
  countSuggestedByDay,
  localDateKey,
  mergeDayCounts,
  startOfMonth,
  weekdayHeaders,
} from "@/lib/reminderCalendar";

type Props = {
  reminders: Todo[];
  calendarEvents?: GoogleCalendarEvent[];
  suggestedReminders?: SuggestedReminder[];
  selectedDay: string;
  visibleMonth: Date;
  onSelectDay: (dayKey: string) => void;
  onVisibleMonthChange: (month: Date) => void;
};

export function ReminderCalendar({
  reminders,
  calendarEvents = [],
  suggestedReminders = [],
  selectedDay,
  visibleMonth,
  onSelectDay,
  onVisibleMonthChange,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const todayKey = localDateKey(new Date());
  const countsByDay = useMemo(
    () =>
      mergeDayCounts(
        countRemindersByDay(reminders),
        countCalendarEventsByDay(calendarEvents),
        countSuggestedByDay(suggestedReminders, todayKey),
      ),
    [calendarEvents, reminders, suggestedReminders, todayKey],
  );
  const cells = useMemo(
    () => buildMonthCells(visibleMonth.getFullYear(), visibleMonth.getMonth()),
    [visibleMonth],
  );
  const weeks = useMemo(() => {
    const rows: typeof cells[] = [];
    for (let i = 0; i < cells.length; i += 7) {
      rows.push(cells.slice(i, i + 7));
    }
    return rows;
  }, [cells]);
  const monthLabel = visibleMonth.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        <Pressable
          style={s.navBtn}
          onPress={() => onVisibleMonthChange(addMonths(visibleMonth, -1))}
          accessibilityRole="button"
          accessibilityLabel={t("calendar.prev_month")}
        >
          <Ionicons name="chevron-back" size={20} color={theme.text} />
        </Pressable>
        <Text style={s.monthLabel}>{monthLabel}</Text>
        <Pressable
          style={s.navBtn}
          onPress={() => onVisibleMonthChange(addMonths(visibleMonth, 1))}
          accessibilityRole="button"
          accessibilityLabel={t("calendar.next_month")}
        >
          <Ionicons name="chevron-forward" size={20} color={theme.text} />
        </Pressable>
      </View>

      <View style={s.weekdayRow}>
        {weekdayHeaders().map((day) => (
          <Text key={day.id} style={s.weekday}>
            {day.label}
          </Text>
        ))}
      </View>

      {weeks.map((week, weekIndex) => (
        <View key={`week-${weekIndex}`} style={s.weekRow}>
          {week.map((cell, cellIndex) => {
            if (!cell.key || cell.day === null) {
              return <View key={`pad-${weekIndex}-${cellIndex}`} style={s.dayCell} />;
            }
            const selected = cell.key === selectedDay;
            const isToday = cell.key === todayKey;
            const count = countsByDay.get(cell.key) ?? 0;
            const cellKey = `${weekIndex}-${cellIndex}-${cell.key}`;
            return (
              <Pressable
                key={cellKey}
                style={[s.dayCell, selected && s.dayCellSelected]}
                onPress={() => onSelectDay(cell.key as string)}
                accessibilityRole="button"
                accessibilityLabel={
                  count > 0
                    ? t("calendar.day_with_items", { day: cell.day, count })
                    : String(cell.day)
                }
              >
                <Text
                  style={[
                    s.dayText,
                    isToday && s.dayTextToday,
                    selected && s.dayTextSelected,
                  ]}
                >
                  {cell.day}
                </Text>
                {count > 0 ? (
                  count > 1 ? (
                    <View style={[s.countBadge, selected && s.countBadgeSelected]}>
                      <Text style={[s.countBadgeText, selected && s.countBadgeTextSelected]}>
                        {count > 9 ? "9+" : count}
                      </Text>
                    </View>
                  ) : (
                    <View style={[s.dot, selected && s.dotSelected]} />
                  )
                ) : (
                  <View style={s.dotSpacer} />
                )}
              </Pressable>
            );
          })}
        </View>
      ))}

      <Pressable
        style={s.todayBtn}
        onPress={() => {
          const today = new Date();
          onVisibleMonthChange(startOfMonth(today));
          onSelectDay(todayKey);
        }}
      >
        <Text style={s.todayBtnText}>{t("calendar.jump_today")}</Text>
      </Pressable>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      backgroundColor: theme.surface,
      borderRadius: 16,
      padding: 12,
      marginBottom: 8,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 8,
    },
    navBtn: {
      width: 36,
      height: 36,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 18,
    },
    monthLabel: {
      fontSize: 17,
      fontWeight: "700",
      color: theme.text,
    },
    weekdayRow: {
      flexDirection: "row",
      marginBottom: 4,
    },
    weekday: {
      flex: 1,
      textAlign: "center",
      fontSize: 12,
      fontWeight: "600",
      color: theme.textTertiary,
    },
    weekRow: {
      flexDirection: "row",
    },
    dayCell: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingVertical: 6,
      borderRadius: 10,
      minHeight: 44,
    },
    dayCellSelected: {
      backgroundColor: theme.primary,
    },
    dayText: {
      fontSize: 15,
      fontWeight: "600",
      color: theme.text,
    },
    dayTextToday: {
      color: theme.primary,
    },
    dayTextSelected: {
      color: theme.onPrimary,
    },
    dot: {
      marginTop: 3,
      minWidth: 6,
      height: 6,
      borderRadius: 3,
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    dotSelected: {
      backgroundColor: theme.onPrimary,
    },
    countBadge: {
      marginTop: 2,
      minWidth: 16,
      height: 14,
      borderRadius: 7,
      paddingHorizontal: 4,
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    countBadgeSelected: {
      backgroundColor: theme.onPrimary,
    },
    countBadgeText: {
      fontSize: 9,
      fontWeight: "800",
      color: theme.onPrimary,
    },
    countBadgeTextSelected: {
      color: theme.primary,
    },
    dotSpacer: {
      height: 9,
    },
    todayBtn: {
      alignSelf: "center",
      marginTop: 8,
      paddingHorizontal: 12,
      paddingVertical: 6,
    },
    todayBtnText: {
      fontSize: 14,
      fontWeight: "600",
      color: theme.primary,
    },
  });
}
