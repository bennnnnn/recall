import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import type { ProjectDailyHistoryDay } from "@/lib/api";
import { localDateKey } from "@/lib/reminderCalendar";
import { Theme, useTheme } from "@/lib/theme";

const WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

type Props = {
  days: ProjectDailyHistoryDay[];
  selectedDate: string;
  onSelectDate: (date: string) => void;
  visibleDays?: number;
};

export function ProjectDailyStrip({
  days,
  selectedDate,
  onSelectDate,
  visibleDays = 7,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const todayKey = useMemo(() => localDateKey(new Date()), []);
  const week = useMemo(() => days.slice(-visibleDays), [days, visibleDays]);

  if (week.length === 0) return null;

  return (
    <View style={s.card} accessibilityRole="summary">
      <Text style={s.title}>{t("projects.daily_strip.title")}</Text>
      <View style={s.row}>
        {week.map((day) => (
          <DayCell
            key={day.date}
            day={day}
            todayKey={todayKey}
            selected={day.date === selectedDate}
            onPress={() => onSelectDate(day.date)}
            theme={theme}
            s={s}
            t={t}
          />
        ))}
      </View>
      <View style={s.legend}>
        <LegendItem color={theme.success} label={t("projects.daily_strip.complete")} theme={theme} />
        <LegendItem color={theme.warning} label={t("projects.daily_strip.partial")} theme={theme} />
        <LegendItem
          color={theme.textTertiary}
          label={t("projects.daily_strip.skipped")}
          theme={theme}
        />
      </View>
    </View>
  );
}

function DayCell({
  day,
  todayKey,
  selected,
  onPress,
  theme,
  s,
  t,
}: {
  day: ProjectDailyHistoryDay;
  todayKey: string;
  selected: boolean;
  onPress: () => void;
  theme: Theme;
  s: ReturnType<typeof makeStyles>;
  t: (key: string, opts?: Record<string, unknown>) => string;
}) {
  const weekdayKey = WEEKDAY_KEYS[day.weekday] ?? "mon";
  const weekdayLabel = t(`projects.daily_strip.${weekdayKey}`);
  const countLabel = t("projects.daily_strip.count", {
    done: day.mastered_count + (day.missed_count ?? 0),
    goal: day.daily_goal,
  });
  const isToday = day.date === todayKey;
  const inactive = day.status === "inactive";

  const complete = day.status === "complete";
  const partial = day.status === "partial";
  const skipped = day.status === "skipped";
  const inProgressToday = day.status === "today";
  const completedCount = day.mastered_count + (day.missed_count ?? 0);
  const todayPartial =
    inProgressToday && completedCount > 0 && !day.goal_met;

  return (
    <Pressable
      style={[s.cell, selected && s.cellSelected]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      accessibilityLabel={`${weekdayLabel}, ${countLabel}, ${t(`projects.daily_strip.${day.status}`)}`}
    >
      <Text style={[s.weekday, isToday && s.weekdayToday, selected && s.weekdaySelected]}>
        {weekdayLabel}
      </Text>
      <View
        style={[
          s.dot,
          inactive && s.inactiveDot,
          complete && s.completeDot,
          partial && s.partialDot,
          todayPartial && s.partialDot,
          skipped && s.skippedDot,
          inProgressToday && !todayPartial && s.todayDot,
          isToday && !complete && !todayPartial && s.todayRing,
          selected && s.dotSelected,
        ]}
      >
        {inactive ? null : complete ? (
          <Ionicons
            name="checkmark"
            size={14}
            color={theme.isDark ? theme.bg : theme.onPrimary}
          />
        ) : partial || todayPartial ? (
          <Text style={s.partialText}>{completedCount}</Text>
        ) : skipped ? (
          <Ionicons name="remove" size={14} color={theme.textTertiary} />
        ) : (
          <Text style={s.todayText}>{completedCount > 0 ? completedCount : "·"}</Text>
        )}
      </View>
    </Pressable>
  );
}

function LegendItem({ color, label, theme }: { color: string; label: string; theme: Theme }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
      <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: color }} />
      <Text style={{ fontSize: 11, color: theme.textSecondary }}>{label}</Text>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    card: {
      backgroundColor: t.surface,
      borderRadius: 18,
      padding: 16,
      gap: 12,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    title: {
      fontSize: 13,
      fontWeight: "700",
      color: t.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    row: {
      flexDirection: "row",
      justifyContent: "space-between",
      gap: 4,
    },
    cell: {
      flex: 1,
      alignItems: "center",
      gap: 6,
      paddingVertical: 4,
      borderRadius: 10,
    },
    cellSelected: { backgroundColor: t.primaryLight },
    weekday: {
      fontSize: 11,
      fontWeight: "700",
      color: t.textSecondary,
    },
    weekdayToday: { color: t.primary },
    weekdaySelected: { color: t.primary },
    muted: { color: t.textTertiary },
    dot: {
      width: 28,
      height: 28,
      borderRadius: 14,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: t.bg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    dotSelected: { borderWidth: 2, borderColor: t.primary },
    completeDot: { backgroundColor: t.success, borderColor: t.success },
    partialDot: { backgroundColor: `${t.warning}33`, borderColor: t.warning },
    skippedDot: { backgroundColor: t.bg, borderColor: t.border },
    todayDot: { backgroundColor: t.primaryLight, borderColor: t.primary },
    todayRing: { borderWidth: 2, borderColor: t.primary },
    inactiveDot: { backgroundColor: t.bg, borderColor: t.border, opacity: 0.35 },
    partialText: { fontSize: 12, fontWeight: "800", color: t.warning },
    todayText: { fontSize: 12, fontWeight: "700", color: t.primary },
    legend: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: 12,
    },
  });
}
