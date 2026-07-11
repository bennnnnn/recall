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
  /** Hide the header progress fraction when the screen already shows it above. */
  hideHeaderSummary?: boolean;
};

/**
 * Learning status colors (one mapping app-wide):
 * - Goal met / complete → theme.success
 * - Correct / mastered → theme.primary
 * - Failed → theme.textTertiary (gray)
 * - Left / pending → theme.warning when > 0
 */
export function ProjectProgressHero({
  stats,
  learnedLabel,
  todayLearnedLabel,
  dueLabel,
  dailyGoal,
  daySnapshot = null,
  streakDays = 0,
  daysInactive,
  hideHeaderSummary = false,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const useDay = daySnapshot != null && daySnapshot.dailyGoal > 0;
  const activeGoal = useDay ? daySnapshot.dailyGoal : dailyGoal;
  const isDaily = activeGoal != null && activeGoal > 0;
  const masteredForDay = useDay ? daySnapshot.masteredCount : stats.mastered_today;
  const missedForDay = useDay
    ? daySnapshot.missedCount
    : (stats.missed_today ?? 0);
  const completedForDay = masteredForDay + missedForDay;
  const goalMet = isDaily && completedForDay >= (activeGoal ?? 0);
  const doneToday = isDaily ? Math.min(completedForDay, activeGoal ?? 0) : stats.mastered_today;
  const leftToday =
    isDaily && !goalMet ? Math.max(0, (activeGoal ?? 0) - completedForDay) : 0;
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
  const leftLabel = goalMet
    ? t("projects.stats.goal_complete")
    : useDay && !daySnapshot.isToday
      ? t("projects.stats.pending_left")
      : t("projects.stats.pending_today");
  const correctLabel = isDaily ? t("projects.stats.correct_day") : todayLearnedLabel;
  const progressHint = isDaily
    ? goalMet
      ? t("projects.list.goal_met_today")
      : t("projects.list.today_remaining", { count: leftToday })
    : null;

  const goalAccent = goalMet
    ? theme.success
    : leftToday > 0
      ? theme.warning
      : theme.textTertiary;

  return (
    <View style={s.card}>
      <View style={s.header}>
        <Text style={s.title}>{cardTitle}</Text>
        {!hideHeaderSummary ? (
          <Text style={[s.pct, goalMet && s.pctComplete]}>
            {isDaily
              ? goalMet
                ? t("projects.daily_goal_done")
                : useDay && !daySnapshot.isToday
                  ? t("projects.daily_progress_day", { done: doneToday, goal: activeGoal })
                  : t("projects.daily_progress", { done: doneToday, goal: activeGoal })
              : t("projects.progress_pct", { pct })}
          </Text>
        ) : progressHint ? (
          <Text style={[s.pct, goalMet && s.pctComplete]}>{progressHint}</Text>
        ) : null}
      </View>
      {isDaily && goalMet && !hideHeaderSummary ? (
        <Text style={s.doneSubtitle}>{t("projects.daily_goal_done_subtitle")}</Text>
      ) : null}
      {useDay && daySnapshot.isToday && streakDays > 0 ? (
        <Text style={s.streakText}>{t("projects.stats.streak", { count: streakDays })}</Text>
      ) : !useDay && streakDays > 0 ? (
        <Text style={s.streakText}>{t("projects.stats.streak", { count: streakDays })}</Text>
      ) : null}
      {gapLabel && (!useDay || daySnapshot.isToday) ? (
        <Text style={s.gapText}>{gapLabel}</Text>
      ) : null}
      <View style={s.track}>
        <View style={[s.fill, goalMet && s.fillComplete, { width: `${pct}%` }]} />
      </View>
      <View style={s.metrics}>
        {isDaily ? (
          <>
            <MetricPill
              label={leftLabel}
              value={goalMet ? (activeGoal ?? 0) : leftToday}
              theme={theme}
              accent={goalAccent}
              highlight={goalMet || leftToday > 0}
              highlightBg={goalMet ? theme.successLight : undefined}
            />
            <MetricPill
              label={correctLabel}
              value={masteredForDay}
              theme={theme}
              accent={theme.primary}
              highlight={goalMet || masteredForDay > 0}
              highlightBg={goalMet || masteredForDay > 0 ? theme.primaryLight : undefined}
            />
            <MetricPill
              label={t("projects.status_missed")}
              value={missedForDay}
              theme={theme}
              accent={theme.textTertiary}
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
              accent={theme.textTertiary}
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
  highlightBg,
}: {
  label: string;
  value: number;
  theme: Theme;
  accent: string;
  highlight?: boolean;
  highlightBg?: string;
}) {
  return (
    <View
      style={{
        flex: 1,
        minWidth: 90,
        backgroundColor: highlight ? (highlightBg ?? theme.primaryLight) : theme.bg,
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
    pctComplete: { color: theme.success },
    doneSubtitle: {
      fontSize: 14,
      fontWeight: "600",
      color: theme.textSecondary,
      lineHeight: 20,
      marginTop: -4,
    },
    streakText: { fontSize: 13, fontWeight: "700", color: theme.textSecondary },
    gapText: { fontSize: 13, fontWeight: "600", color: theme.warning },
    track: {
      height: 8,
      borderRadius: 4,
      backgroundColor: theme.border,
      overflow: "hidden",
    },
    fill: { height: 8, borderRadius: 4, backgroundColor: theme.primary },
    fillComplete: { backgroundColor: theme.success },
    metrics: { flexDirection: "row", flexWrap: "wrap", gap: 16 },
  });
}
