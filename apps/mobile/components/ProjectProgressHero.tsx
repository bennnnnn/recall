import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import type { ProjectStats } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  stats: ProjectStats;
  learnedLabel: string;
  todayLearnedLabel: string;
  dueLabel: string;
  /** When set, shows today's batch progress instead of lifetime %. */
  dailyGoal?: number;
};

export function ProjectProgressHero({
  stats,
  learnedLabel,
  todayLearnedLabel,
  dueLabel,
  dailyGoal,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const isDaily = dailyGoal != null && dailyGoal > 0;
  const goalMet = isDaily && stats.mastered_today >= dailyGoal;
  const doneToday = isDaily ? Math.min(stats.mastered_today, dailyGoal) : stats.mastered_today;
  const leftToday =
    isDaily && !goalMet ? Math.max(0, dailyGoal - stats.mastered_today) : 0;
  const pct = isDaily
    ? Math.min(100, Math.round((doneToday / dailyGoal) * 100))
    : stats.total > 0
      ? Math.min(100, Math.round((stats.mastered_count / stats.total) * 100))
      : 0;
  const hasDue = stats.due_for_review > 0;

  return (
    <View style={s.card}>
      <View style={s.header}>
        <Text style={s.title}>
          {isDaily ? t("projects.stats.today") : t("projects.progress_title")}
        </Text>
        <Text style={s.pct}>
          {isDaily
            ? goalMet
              ? t("projects.daily_goal_done")
              : t("projects.daily_progress", { done: doneToday, goal: dailyGoal })
            : t("projects.progress_pct", { pct })}
        </Text>
      </View>
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
              value={goalMet ? dailyGoal : leftToday}
              theme={theme}
              accent={goalMet ? theme.primary : leftToday > 0 ? theme.warning : theme.textTertiary}
              highlight={!goalMet && leftToday > 0}
            />
            <MetricPill
              label={todayLearnedLabel}
              value={stats.mastered_today}
              theme={theme}
              accent={theme.primary}
            />
            <MetricPill
              label={t("projects.status_learning")}
              value={stats.learning_count}
              theme={theme}
              accent={theme.warning}
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
              label={t("projects.status_learning")}
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
