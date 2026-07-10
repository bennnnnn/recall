import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import type { Project, ProjectDetail } from "@/lib/api";
import { resolveDailyGoal } from "@/lib/dailyGoals";
import { isLanguageProject } from "@/lib/languageLevels";
import { fetchProjectDetail } from "@/lib/projectDetailCache";
import { isTriviaProject } from "@/lib/projectUi";
import { Theme, useTheme } from "@/lib/theme";
import {
  LearningDropdownDivider,
  LearningDropdownRow,
} from "@/components/projects/LearningDropdownRow";

type Props = {
  project: Project;
  token: string;
  icon: keyof typeof Ionicons.glyphMap;
  onOpen: () => void;
  onLevelPress: () => void;
  onDailyPress: () => void;
  onTopicsPress?: () => void;
  levelLabel: string;
  dailyLabel: string;
  topicsLabel?: string;
  saving?: boolean;
};

function cardTitle(
  project: Project,
  t: (key: string) => string,
): string {
  if (isLanguageProject(project.kind)) {
    return t("projects.list.english_title");
  }
  if (isTriviaProject(project.kind)) {
    return t("projects.trivia.title");
  }
  return project.title;
}

export function LearningProjectCard({
  project,
  token,
  icon,
  onOpen,
  onLevelPress,
  onDailyPress,
  onTopicsPress,
  levelLabel,
  dailyLabel,
  topicsLabel,
  saving = false,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [detail, setDetail] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void fetchProjectDetail(token, project.id).then((data) => {
      if (cancelled) return;
      setDetail(data);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [token, project.id]);

  const stats = detail?.stats;
  const dailyGoal = resolveDailyGoal(project.daily_goal);
  const isLang = isLanguageProject(project.kind);
  const isTrivia = isTriviaProject(project.kind);
  const levelField = isTrivia
    ? t("projects.list.difficulty_short")
    : t("projects.list.level_short");
  const dailyField = isTrivia
    ? t("projects.list.daily_questions")
    : t("projects.list.daily_words");

  const lifetimeTotal = stats?.mastered_count ?? 0;
  const showLifetimeBadge = isLang || isTrivia;
  const lifetimeBadgeLabel = isTrivia
    ? t("projects.list.total_facts")
    : t("projects.list.total_vocabularies");

  const todayParts: string[] = [];
  const showTodayLine = stats != null && (isLang || isTrivia);
  const todayGoalMet = showTodayLine && stats.mastered_today >= dailyGoal;
  if (showTodayLine) {
    todayParts.push(t("projects.list.today_line", { done: stats.mastered_today, goal: dailyGoal }));
  }

  return (
    <View style={s.section}>
      {showLifetimeBadge ? (
        <View style={s.lifetimeBadge}>
          {loading ? (
            <ActivityIndicator size="small" color={theme.primary} />
          ) : (
            <>
              <Text style={s.lifetimeBadgeLabel}>{lifetimeBadgeLabel}</Text>
              <Text style={s.lifetimeBadgeCount}>{lifetimeTotal}</Text>
            </>
          )}
        </View>
      ) : null}

      <View style={s.card}>
        <Pressable style={s.header} onPress={onOpen}>
          <View style={s.iconWrap}>
            <Ionicons name={icon} size={22} color={theme.primary} />
          </View>
          <Text style={s.headerTitle} numberOfLines={1}>
            {cardTitle(project, t)}
          </Text>
          <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
        </Pressable>

        {loading && !showLifetimeBadge ? (
          <View style={s.loadingRow}>
            <ActivityIndicator size="small" color={theme.primary} />
            <Text style={s.loadingText}>{t("projects.list.loading_stats")}</Text>
          </View>
        ) : !loading && stats && todayParts.length > 0 ? (
          <View style={[s.todayWrap, todayGoalMet ? s.todayWrapComplete : s.todayWrapPending]}>
            <Text style={[s.todayLine, todayGoalMet ? s.todayLineComplete : s.todayLinePending]}>
              {todayParts.join(" · ")}
            </Text>
          </View>
        ) : null}

        <View style={s.dropdowns}>
        <LearningDropdownRow
          label={levelField}
          value={levelLabel}
          onPress={onLevelPress}
          disabled={saving}
        />
        <LearningDropdownDivider />
        <LearningDropdownRow
          label={dailyField}
          value={dailyLabel}
          onPress={onDailyPress}
          disabled={saving}
        />
        {isTrivia && onTopicsPress && topicsLabel ? (
          <>
            <LearningDropdownDivider />
            <LearningDropdownRow
              label={t("projects.list.topics_row")}
              value={topicsLabel}
              onPress={onTopicsPress}
              disabled={saving}
            />
          </>
        ) : null}
        </View>
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    section: {
      gap: 10,
      marginBottom: 20,
    },
    lifetimeBadge: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingVertical: 14,
      paddingHorizontal: 16,
      borderRadius: 12,
      borderWidth: 1,
      borderStyle: "dashed",
      borderColor: theme.primary,
      backgroundColor: theme.bg,
      minHeight: 52,
    },
    lifetimeBadgeLabel: {
      fontSize: 15,
      fontWeight: "600",
      color: theme.textSecondary,
    },
    lifetimeBadgeCount: {
      fontSize: 28,
      fontWeight: "800",
      color: theme.text,
      letterSpacing: -0.5,
    },
    card: {
      borderRadius: 16,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      overflow: "hidden",
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingVertical: 14,
      paddingHorizontal: 16,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
    },
    iconWrap: {
      width: 44,
      height: 44,
      borderRadius: 12,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    headerTitle: {
      flex: 1,
      fontSize: 17,
      fontWeight: "700",
      color: theme.text,
    },
    loadingRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      paddingHorizontal: 16,
      paddingVertical: 16,
    },
    loadingText: { fontSize: 14, color: theme.textSecondary },
    todayWrap: {
      paddingVertical: 13,
      paddingHorizontal: 16,
    },
    todayWrapPending: {
      backgroundColor: theme.dangerLight,
    },
    todayWrapComplete: {
      backgroundColor: theme.isDark ? "#142A1A" : "#F0FDF4",
    },
    todayLine: {
      fontSize: 14,
      fontWeight: "600",
      lineHeight: 20,
    },
    todayLinePending: {
      color: theme.isDark ? "#FF9B94" : "#B42318",
    },
    todayLineComplete: {
      color: theme.isDark ? "#4ADE80" : "#15803D",
    },
    dropdowns: {
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
    },
  });
}
