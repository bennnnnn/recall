import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import type { ProjectStats } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";

export type ProjectDaySnapshot = {
  title: string;
  masteredCount: number;
  missedCount: number;
  dailyGoal: number;
  isToday: boolean;
};

type Props = {
  stats: ProjectStats;
  learnedLabel: string;
  todayLearnedLabel: string;
  dueLabel: string;
  /** When set, shows today's batch progress instead of lifetime %. */
  dailyGoal?: number;
  daySnapshot?: ProjectDaySnapshot | null;
  streakDays?: number;
  daysInactive?: number | null;
};

export function ProjectProgressHero({
  stats,
  learnedLabel,
  todayLearnedLabel,
  dueLabel,
  dailyGoal,
  daySnapshot = null,
  streakDays = 0,
  daysInactive,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const useDay = daySnapshot != null && daySnapshot.dailyGoal > 0;
  const activeGoal = useDay ? daySnapshot.dailyGoal : dailyGoal;
  const isDaily = activeGoal != null && activeGoal > 0;
  const masteredForDay = useDay ? daySnapshot.masteredCount : stats.mastered_today;
  const missedForDay = useDay ? daySnapshot.missedCount : stats.learning_count;
  const goalMet = isDaily && masteredForDay >= (activeGoal ?? 0);
  const doneToday = isDaily ? Math.min(masteredForDay, activeGoal ?? 0) : stats.mastered_today;
  const leftToday =
    isDaily && !goalMet ? Math.max(0, (activeGoal ?? 0) - masteredForDay) : 0;
  const pct = isDaily
    ? Math.min(100, Math.round((doneToday / (activeGoal ?? 1)) * 100))
    : stats.total > 0
      ? Math.min(100, Math.round((stats.mastered_count / stats.total) * 100))
      : 0;
  const hasDue = stats.due_for_review > 0;
  const gapLabel =
    daysInactive != null && daysInactive >= 2
      ? t("projects.stats.inactive_days", { days: daysInactive })
      : null;
  const cardTitle = useDay
    ? daySnapshot.title
    : isDaily
      ? t("projects.stats.today")
      : t("projects.progress_title");

  return (
    <View style={s.card}>
      <View style={s.header}>
        <Text style={s.title}>{cardTitle}</Text>
        <Text style={s.pct}>
          {isDaily
            ? goalMet
              ? t("projects.daily_goal_done")
              : t("projects.daily_progress", { done: doneToday, goal: activeGoal })
            : t("projects.progress_pct", { pct })}
        </Text>
      </View>
      {useDay && daySnapshot.isToday && streakDays > 0 ? (
        <Text style={s.streakText}>{t("projects.stats.streak", { count: streakDays })}</Text>
      ) : !useDay && streakDays > 0 ? (
        <Text style={s.streakText}>{t("projects.stats.streak", { count: streakDays })}</Text>
      ) : null}
      {gapLabel && (!useDay || daySnapshot.isToday) ? (
        <Text style={s.gapText}>{gapLabel}</Text>
      ) : null}
      <View style={s.track}>
        <View style={[s.fill, { width: `${pct}%` }]} />
      </View>
      <View style={s.metrics}>
        {isDaily ? (
          <>
            <MetricPill
              label={
                goalMet ? t("projects.stats.goal_complete") : t("projects.stats.pending_today")
              }
              value={goalMet ? (activeGoal ?? 0) : leftToday}
              theme={theme}
              accent={goalMet ? theme.primary : leftToday > 0 ? theme.warning : theme.textTertiary}
              highlight={!goalMet && leftToday > 0}
            />
            <MetricPill
              label={todayLearnedLabel}
              value={masteredForDay}
              theme={theme}
              accent={theme.primary}
            />
            <MetricPill
              label={t("projects.status_missed")}
              value={missedForDay}
              theme={theme}
              accent={missedForDay > 0 ? theme.warning : theme.textTertiary}
              highlight={missedForDay > 0}
            />
          </>
        ) : (
          <>
            <MetricPill
              label={learnedLabel}
              value={stats.mastered_count}
              theme={theme}
              accent={theme.primary}
            />
            <MetricPill
              label={t("projects.status_missed")}
              value={stats.learning_count}
              theme={theme}
              accent={theme.warning}
            />
            <MetricPill
              label={dueLabel}
              value={stats.due_for_review}
              theme={theme}
              accent={hasDue ? theme.primary : theme.textTertiary}
              highlight={hasDue}
            />
          </>
        )}
      </View>
    </View>
  );
}

function MetricPill({
  label,
  value,
  theme,
  accent,
  highlight = false,
}: {
  label: string;
  value: number;
  theme: Theme;
  accent: string;
  highlight?: boolean;
}) {
  return (
    <View
      style={{
        flex: 1,
        minWidth: 90,
        backgroundColor: highlight ? theme.primaryLight : theme.bg,
        borderRadius: 12,
        paddingVertical: 10,
        paddingHorizontal: 8,
        alignItems: "center",
        gap: 2,
      }}
    >
      <Text style={{ fontSize: 18, fontWeight: "800", color: accent }}>{value}</Text>
      <Text
        style={{
          fontSize: 10,
          fontWeight: "700",
          color: theme.textSecondary,
          textAlign: "center",
        }}
        numberOfLines={2}
      >
        {label}
      </Text>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    card: {
      backgroundColor: theme.surface,
      borderRadius: 18,
      padding: 16,
      gap: 12,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
    title: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    pct: { fontSize: 14, fontWeight: "800", color: theme.primary },
    streakText: { fontSize: 13, fontWeight: "700", color: theme.primary },
    gapText: { fontSize: 13, fontWeight: "600", color: theme.warning },
    track: {
      height: 8,
      borderRadius: 4,
      backgroundColor: theme.border,
      overflow: "hidden",
    },
    fill: { height: 8, borderRadius: 4, backgroundColor: theme.primary },
    metrics: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  });
}
