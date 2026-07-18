import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { LearningContinueCta } from "@/components/projects/LearningContinueCta";
import type { Project } from "@/lib/api";
import { resolveDailyGoal } from "@/lib/dailyGoals";
import { isLanguageProject } from "@/lib/languageLevels";
import { isTriviaProject, learningProjectTitle } from "@/lib/projectUi";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  project: Project;
  icon: keyof typeof Ionicons.glyphMap;
  onOpen: () => void;
  onStudy?: () => void;
  onReview?: () => void;
  levelLabel: string;
  dailyLabel: string;
  topicsChip?: string;
};

export function LearningProjectCard({
  project,
  icon,
  onOpen,
  onStudy,
  onReview,
  levelLabel,
  dailyLabel,
  topicsChip,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  const stats = project.stats;
  const dailyGoal = resolveDailyGoal(project.daily_goal);
  const isLang = isLanguageProject(project.kind);
  const isTrivia = isTriviaProject(project.kind);
  const showLearningUi = isLang || isTrivia;

  const lifetimeTotal = stats?.mastered_count ?? 0;
  const masteredToday = stats?.mastered_today ?? 0;
  const missedToday = stats?.missed_today ?? 0;
  const completedToday = masteredToday + missedToday;
  const dueForReview = stats?.due_for_review ?? 0;
  const streakDays = stats?.streak_days ?? 0;
  const goalMet = stats != null && completedToday >= dailyGoal;
  const remaining = Math.max(0, dailyGoal - completedToday);
  const progressPct =
    dailyGoal > 0
      ? Math.min(100, Math.round((Math.min(completedToday, dailyGoal) / dailyGoal) * 100))
      : 0;

  const lifetimeLine = isTrivia
    ? t("projects.list.lifetime_facts", { count: lifetimeTotal })
    : t("projects.list.lifetime_words", { count: lifetimeTotal });

  const chips = [levelLabel, `${dailyLabel}/day`, ...(topicsChip ? [topicsChip] : [])];

  const ctaLabel =
    showLearningUi && stats
      ? !goalMet && remaining > 0 && onStudy
        ? masteredToday === 0 && missedToday === 0
          ? isTrivia
            ? t("projects.study.start_questions")
            : t("projects.study.start_words", { count: dailyGoal })
          : isTrivia
            ? t("projects.list.continue_questions", { count: remaining })
            : t("projects.list.continue_words", { count: remaining })
        : goalMet && dueForReview > 0 && onReview
          ? isTrivia
            ? t("projects.list.review_facts", { count: dueForReview })
            : t("projects.list.review_words", { count: dueForReview })
          : null
      : null;
  const ctaAction =
    ctaLabel && !goalMet && remaining > 0 && onStudy
      ? onStudy
      : ctaLabel && goalMet && dueForReview > 0 && onReview
        ? onReview
        : undefined;

  return (
    <View style={s.section}>
      <View style={s.card}>
        <Pressable style={s.mainTap} onPress={onOpen}>
          <View style={s.header}>
            <View style={s.iconWrap}>
              <Ionicons name={icon} size={22} color={theme.primary} />
            </View>
            <View style={s.headerText}>
              <Text style={s.headerTitle} numberOfLines={1}>
                {learningProjectTitle(project.kind, t, project.title)}
              </Text>
              {showLearningUi ? (
                <Text style={s.headerSubtitle} numberOfLines={2}>
                  {lifetimeLine}
                </Text>
              ) : null}
            </View>
            <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
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
              <View style={s.track}>
                <View
                  style={[
                    s.fill,
                    goalMet && s.fillComplete,
                    { width: `${progressPct}%` },
                  ]}
                />
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
            </View>
          ) : null}
        </Pressable>

        {ctaLabel && ctaAction ? (
          <LearningContinueCta
            label={ctaLabel}
            onPress={ctaAction}
            embedded
            progress={{ completedToday, dailyGoal }}
          />
        ) : null}
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    section: {
      marginBottom: 24,
    },
    card: {
      borderRadius: 16,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      overflow: "hidden",
    },
    mainTap: {
      gap: 12,
      paddingBottom: 14,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingTop: 14,
      paddingHorizontal: 16,
    },
    iconWrap: {
      width: 44,
      height: 44,
      borderRadius: 12,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    headerText: {
      flex: 1,
      gap: 2,
    },
    headerTitle: {
      fontSize: 16,
      fontWeight: "700",
      color: theme.text,
    },
    headerSubtitle: {
      fontSize: 13,
      fontWeight: "500",
      // Same primary ink as Lists / Reminders body text — not muted gray.
      color: theme.text,
      lineHeight: 18,
    },
    progressBlock: {
      paddingHorizontal: 16,
      gap: 8,
    },
    progressMeta: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 8,
    },
    progressLabel: {
      fontSize: 13,
      fontWeight: "600",
      color: theme.text,
    },
    progressLabelComplete: {
      color: theme.success,
    },
    streakText: {
      fontSize: 12,
      fontWeight: "600",
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
      gap: 8,
      paddingHorizontal: 16,
    },
    chip: {
      backgroundColor: theme.bg,
      borderRadius: 999,
      paddingHorizontal: 10,
      paddingVertical: 5,
      maxWidth: "100%",
    },
    chipText: {
      fontSize: 12,
      fontWeight: "600",
      color: theme.text,
    },
  });
}
