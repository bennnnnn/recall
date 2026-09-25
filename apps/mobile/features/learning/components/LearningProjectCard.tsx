import { memo, useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import type { Learning } from "@/lib/api";
import { resolveDailyGoal } from "@/features/learning/model/dailyGoals";
import { IconSize, type IoniconName } from "@/lib/icons";
import { isLanguageProject } from "@/features/learning/model/languageLevels";
import { learningProjectTitle } from "@/features/learning/model/projectUi";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

type Props = {
  project: Learning;
  icon: IoniconName;
  onOpen: (projectId: string) => void;
  dailyLabel: string;
};

export const LearningProjectCard = memo(function LearningProjectCard({
  project,
  icon,
  onOpen,
  dailyLabel,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  const stats = project.stats;
  const dailyGoal = resolveDailyGoal(project.daily_goal);
  const isLang = isLanguageProject(project.kind);
  const showLearningUi = isLang;

  const lifetimeTotal = stats?.mastered_count ?? 0;
  const masteredToday = stats?.mastered_today ?? 0;
  const missedToday = stats?.missed_today ?? 0;
  const completedToday = stats?.completed_today ?? masteredToday + missedToday;
  const streakDays = stats?.streak_days ?? 0;
  const goalMet = stats != null && completedToday >= dailyGoal;
  const progressPct =
    dailyGoal > 0
      ? Math.min(100, Math.round((Math.min(completedToday, dailyGoal) / dailyGoal) * 100))
      : 0;

  const lifetimeLine = t("projects.list.lifetime_words", { count: lifetimeTotal });

  const chips = [t("lesson.daily_goal", { count: Number(dailyLabel) })];

  return (
    <View style={s.section}>
      <View style={s.card}>
        <Pressable accessibilityRole="button" style={s.mainTap} onPress={() => onOpen(project.id)}>
          <View style={s.header}>
            <View style={s.iconWrap}>
              <Icon name={icon} size={IconSize.md} color={theme.primary} />
            </View>
            <View style={s.headerText}>
              <Text style={s.headerTitle} numberOfLines={1}>
                {learningProjectTitle(project.kind, t, project.title, project.target_language)}
              </Text>
              {showLearningUi ? (
                <Text style={s.headerSubtitle} numberOfLines={2}>
                  {lifetimeLine}
                </Text>
              ) : null}
            </View>
            <Icon name="chevron-forward" size={18} color={theme.textTertiary} />
          </View>

          {showLearningUi && stats ? (
            <View style={s.progressBlock}>
              <View style={s.progressMeta}>
                <Text style={[s.progressLabel, goalMet && s.progressLabelComplete]}>
                  {goalMet
                    ? t("projects.list.goal_met_today")
                    : t("projects.list.today_progress", { done: completedToday, goal: dailyGoal })}
                </Text>
                {streakDays > 0 ? (
                  <Text style={s.streakText}>
                    {t("projects.stats.streak", { count: streakDays })}
                  </Text>
                ) : null}
              </View>
              <View
                style={s.track}
                accessibilityRole="progressbar"
                accessibilityValue={{
                  min: 0,
                  max: dailyGoal,
                  now: Math.min(completedToday, dailyGoal),
                }}
              >
                <View style={[s.fill, goalMet && s.fillComplete, { width: `${progressPct}%` }]} />
              </View>
            </View>
          ) : null}

          {showLearningUi ? (
            <View style={s.chipRow}>
              {chips.map((chip) => (
                <View key={chip} style={s.chip}>
                  <Text style={s.chipText} numberOfLines={1}>
                    {chip}
                  </Text>
                </View>
              ))}
              <Text style={s.continueText}>{t("lesson.open_map")}</Text>
            </View>
          ) : null}
        </Pressable>
      </View>
    </View>
  );
});

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    continueText: {
      ...Type.compact,
      ...Weight.bold,
      color: theme.primary,
      paddingVertical: 5,
      marginLeft: "auto",
    },
    section: {
      marginBottom: 0,
    },
    card: {
      borderRadius: Radius.xl,
      backgroundColor: theme.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      overflow: "hidden",
    },
    mainTap: {
      gap: Space.sm,
      paddingBottom: 14,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingTop: 14,
      paddingHorizontal: Space.md,
    },
    iconWrap: {
      width: 44,
      height: 44,
      borderRadius: Radius.md,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    headerText: {
      flex: 1,
      gap: 2,
    },
    headerTitle: {
      ...Type.body,
      ...Weight.bold,
      color: theme.text,
    },
    headerSubtitle: {
      ...Type.compact,
      ...Weight.medium,
      // Same primary ink as Lists / Reminders body text — not muted gray.
      color: theme.text,
      lineHeight: 18,
    },
    progressBlock: {
      paddingHorizontal: Space.md,
      gap: Space.xs,
    },
    progressMeta: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: Space.xs,
    },
    progressLabel: {
      ...Type.compact,
      ...Weight.semibold,
      color: theme.text,
    },
    progressLabelComplete: {
      color: theme.success,
    },
    streakText: {
      ...Type.caption,
      ...Weight.semibold,
      color: theme.textSecondary,
    },
    track: {
      height: 6,
      borderRadius: 3,
      backgroundColor: theme.border,
      overflow: "hidden",
    },
    fill: {
      height: 6,
      borderRadius: 3,
      backgroundColor: theme.primary,
    },
    fillComplete: {
      backgroundColor: theme.success,
    },
    chipRow: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: Space.xs,
      paddingHorizontal: Space.md,
    },
    chip: {
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      borderRadius: Radius.full,
      paddingHorizontal: 10,
      paddingVertical: 5,
      maxWidth: "100%",
    },
    chipText: {
      ...Type.caption,
      ...Weight.semibold,
      color: theme.text,
    },
  });
}
