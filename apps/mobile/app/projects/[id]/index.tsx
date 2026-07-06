import { useCallback, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Redirect, useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { ProjectDailyStrip } from "@/components/ProjectDailyStrip";
import { ProjectDayItemsList, type ProjectStudyAction } from "@/components/ProjectDayItemsList";
import { ProjectProgressHero } from "@/components/ProjectProgressHero";
import { ProjectItemRow } from "@/components/ProjectItemRow";
import { useAuth } from "@/contexts/AuthContext";
import { api, type ProjectDetail, type VocabStatus } from "@/lib/api";
import { queueChatLaunch, queueDailyQuizLaunch } from "@/lib/chatLaunch";
import {
  isLanguageProject,
  levelLabel,
} from "@/lib/languageLevels";
import { resolveDailyGoal } from "@/lib/dailyGoals";
import { localDateKey } from "@/lib/reminderCalendar";
import {
  buildProjectBonusQuestionsPrompt,
  buildProjectBonusWordsPrompt,
  isDailyGoalMet,
  remainingDailyGoal,
} from "@/lib/projectChat";
import { formatProjectListTitle, isConceptProject, isTriviaProject, projectStatsLabels } from "@/lib/projectUi";
import {
  formatTriviaTopicLabels,
  parseTriviaTopics,
} from "@/lib/triviaTopics";
import { Theme, useTheme } from "@/lib/theme";

export default function ProjectDetailScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const hasLoadedRef = useRef(false);
  const [selectedDay, setSelectedDay] = useState(() => localDateKey(new Date()));
  const [conceptBusyId, setConceptBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token || typeof id !== "string") return;
    const firstLoad = !hasLoadedRef.current;
    if (firstLoad) setLoading(true);
    setLoadError(false);
    try {
      const data = await api.getProject(token, id);
      setProject(data);
      if (data.kind === "programming") {
        router.replace("/projects");
      }
    } catch {
      setProject(null);
      setLoadError(true);
    } finally {
      hasLoadedRef.current = true;
      if (firstLoad) setLoading(false);
    }
  }, [token, id, router]);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  if (!token) return <Redirect href="/login" />;

  const confirmDelete = () => {
    if (!token || !project) return;
    Alert.alert(t("projects.delete_title"), t("projects.delete_body"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"),
        style: "destructive",
        onPress: async () => {
          try {
            await api.deleteProject(token, project.id);
            router.back();
          } catch {
            Alert.alert(t("common.error"), t("projects.delete_failed"));
          }
        },
      },
    ]);
  };

  if (loading && !project) {
    return (
      <View style={s.center}>
        <ActivityIndicator color={theme.primary} />
      </View>
    );
  }

  if (!project) {
    return (
      <View style={s.center}>
        <Text style={s.empty}>
          {loadError ? t("projects.load_failed") : t("projects.not_found")}
        </Text>
        {loadError ? (
          <Pressable style={s.retryBtn} onPress={() => void load()}>
            <Text style={s.retryText}>{t("common.retry")}</Text>
          </Pressable>
        ) : null}
      </View>
    );
  }

  const isLang = isLanguageProject(project.kind);
  const isTrivia = isTriviaProject(project.kind);
  const isConcept = isConceptProject(project.kind) && !isTrivia;
  const stats = project.stats;
  const statLabels = projectStatsLabels(project.kind, t);
  const dailyGoal = isLang || isTrivia ? resolveDailyGoal(project.daily_goal) : undefined;
  const dailyGoalMet = isDailyGoalMet(project);
  const selectedDayMeta = project.daily_history?.find((day) => day.date === selectedDay);
  const showDailyTracking = (isLang || isTrivia) && (project.daily_history?.length ?? 0) > 0;
  const isToday = selectedDay === localDateKey(new Date());
  const remainingToday = dailyGoal ? remainingDailyGoal(project) : 0;

  const handleConceptStatusChange = async (itemId: string, status: VocabStatus) => {
    if (!token || typeof id !== "string") return;
    setConceptBusyId(itemId);
    try {
      await api.updateProjectItem(token, id, itemId, { status });
      await load();
    } catch {
      Alert.alert(t("common.error"), t("projects.status_update_failed"));
    } finally {
      setConceptBusyId(null);
    }
  };

  const startStudyQuiz = () => {
    if (isTrivia) {
      queueDailyQuizLaunch(project.id, "trivia");
    } else if (isLang) {
      queueDailyQuizLaunch(project.id, "vocab", "en");
    }
    router.replace("/");
  };

  const startStudyBonus = () => {
    if (isTrivia) {
      queueChatLaunch(buildProjectBonusQuestionsPrompt(project), project.id, undefined, "trivia", "chat");
    } else if (isLang) {
      queueChatLaunch(buildProjectBonusWordsPrompt(project), project.id, "en");
    }
    router.replace("/");
  };

  let todayStudyAction: ProjectStudyAction | null = null;
  if ((isLang || isTrivia) && dailyGoal && isToday) {
    if (dailyGoalMet) {
      todayStudyAction = {
        label: isTrivia ? t("projects.add_bonus_questions") : t("projects.add_bonus_words"),
        onPress: startStudyBonus,
      };
    } else if (stats.mastered_today === 0) {
      todayStudyAction = {
        label: isTrivia
          ? t("projects.study.start_questions", { count: dailyGoal })
          : t("projects.study.start_words", { count: dailyGoal }),
        onPress: startStudyQuiz,
      };
    } else {
      todayStudyAction = {
        label: isTrivia
          ? t("projects.study.complete_questions", { count: remainingToday })
          : t("projects.study.complete_words", { count: remainingToday }),
        onPress: startStudyQuiz,
      };
    }
  }

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content}>
      <View style={s.hero}>
        <View style={s.badgeRow}>
          <View style={s.badgeRowLeft}>
            <View style={s.badge}>
              <Text style={s.badgeText}>
                {isLang
                  ? t("projects.kind.language")
                  : isTrivia
                    ? t("projects.kind.trivia")
                    : t(`projects.kind.${project.kind}`)}
              </Text>
            </View>
            {isLang ? (
              <View style={s.badge}>
                <Text style={s.badgeText}>{levelLabel(project.level)}</Text>
              </View>
            ) : null}
          </View>
          {isLang || isTrivia ? (
            <View style={s.dayWordCountBox}>
              <Text style={s.dayWordCountText}>
                {isTrivia
                  ? t("projects.daily_items.fact_count", { count: stats.mastered_count })
                  : t("projects.daily_items.word_count", { count: stats.mastered_count })}
              </Text>
            </View>
          ) : null}
        </View>
        {(isLang || isTrivia) && dailyGoal ? (
          <View style={s.dailyGoalHeadline}>
            <Text style={s.dailyGoalNumber}>{dailyGoal}</Text>
            <Text style={s.dailyGoalLabel}>
              {isTrivia
                ? t("projects.trivia.daily_goal_headline_label")
                : t("projects.daily_goal_headline_label")}
            </Text>
          </View>
        ) : (
          <Text style={s.title}>{project.title}</Text>
        )}
        {isTrivia ? (
          <Text style={s.description}>
            {formatTriviaTopicLabels(parseTriviaTopics(project.description), t)}
          </Text>
        ) : project.description ? (
          <Text style={s.description}>{project.description}</Text>
        ) : null}
      </View>

      <ProjectProgressHero
        stats={stats}
        learnedLabel={statLabels.learned}
        todayLearnedLabel={statLabels.learnedToday}
        dueLabel={statLabels.due}
        dailyGoal={dailyGoal}
      />

      {showDailyTracking ? (
        <ProjectDailyStrip
          days={project.daily_history ?? []}
          selectedDate={selectedDay}
          onSelectDate={setSelectedDay}
        />
      ) : null}

      {showDailyTracking && token ? (
        <ProjectDayItemsList
          token={token}
          projectId={project.id}
          activityDate={selectedDay}
          dayMeta={selectedDayMeta}
          isTrivia={isTrivia}
          itemsByDate={project.daily_items_by_date ?? {}}
          studyAction={todayStudyAction}
          onItemUpdated={load}
        />
      ) : null}

      {isConcept ? (
        <>
          {project.lists.length > 0 ? (
            project.lists.map((group) => (
              <View key={group.list_title} style={s.listSection}>
                <Text style={s.listTitle}>
                  {formatProjectListTitle(group.list_title, project.kind, t)}
                </Text>
                {group.items.map((item) => (
                  <ProjectItemRow
                    key={item.id}
                    item={item}
                    showSpeech={false}
                    busy={conceptBusyId === item.id}
                    onStatusChange={(status) => handleConceptStatusChange(item.id, status)}
                  />
                ))}
              </View>
            ))
          ) : (
            <View style={s.comingSoon}>
              <Text style={s.comingSoonBody}>
                {t(project.kind === "math" ? "projects.math_empty" : "projects.concept_empty")}
              </Text>
            </View>
          )}
        </>
      ) : null}

      <Pressable style={s.deleteBtn} onPress={confirmDelete}>
        <Text style={s.deleteBtnText}>{t("projects.delete")}</Text>
      </Pressable>
    </ScrollView>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: theme.bg },
    center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.bg },
    content: { padding: 16, gap: 16, paddingBottom: 40 },
    empty: { fontSize: 15, color: theme.textSecondary, textAlign: "center", paddingHorizontal: 24 },
    retryBtn: {
      marginTop: 12,
      paddingHorizontal: 16,
      paddingVertical: 8,
      borderRadius: 999,
      backgroundColor: theme.primaryLight,
    },
    retryText: { fontSize: 14, fontWeight: "600", color: theme.primary },
    hero: { gap: 8 },
    badgeRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10 },
    badgeRowLeft: { flexDirection: "row", flexWrap: "wrap", gap: 8, flex: 1 },
    dayWordCountBox: {
      borderWidth: 1,
      borderStyle: "dashed",
      borderColor: theme.primary,
      borderRadius: 10,
      paddingHorizontal: 10,
      paddingVertical: 6,
      flexShrink: 0,
    },
    dayWordCountText: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.primary,
    },
    badge: {
      backgroundColor: theme.primaryLight,
      borderRadius: 999,
      paddingHorizontal: 10,
      paddingVertical: 4,
    },
    badgeText: { fontSize: 12, fontWeight: "700", color: theme.primary },
    dailyGoalHeadline: {
      flexDirection: "row",
      alignItems: "baseline",
      gap: 8,
      marginTop: 2,
    },
    dailyGoalNumber: {
      fontSize: 28,
      fontWeight: "600",
      color: theme.primary,
      letterSpacing: -1,
      lineHeight: 32,
    },
    dailyGoalLabel: {
      fontSize: 12,
      fontWeight: "500",
      color: theme.textSecondary,
      textTransform: "uppercase",
      letterSpacing: 0.8,
    },
    title: { fontSize: 28, fontWeight: "800", color: theme.text, letterSpacing: -0.5 },
    description: { fontSize: 16, lineHeight: 24, color: theme.textSecondary },
    statsSection: {
      backgroundColor: theme.surface,
      borderRadius: 16,
      padding: 14,
      gap: 10,
    },
    statsHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
    statsHeaderTitle: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    statsSummary: { fontSize: 14, lineHeight: 20, color: theme.textSecondary },
    statsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
    statCard: {
      width: "47%",
      flexGrow: 1,
      backgroundColor: theme.bg,
      borderRadius: 14,
      padding: 14,
      alignItems: "center",
      gap: 4,
    },
    statValue: { fontSize: 22, fontWeight: "800", color: theme.text },
    statHighlight: { color: theme.primary },
    statLabel: { fontSize: 11, fontWeight: "600", color: theme.textSecondary, textAlign: "center" },
    listSection: {
      backgroundColor: theme.surface,
      borderRadius: 16,
      padding: 14,
      gap: 10,
    },
    listTitle: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    itemRow: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
    itemMain: { flex: 1, gap: 2 },
    itemTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
    itemContent: { fontSize: 16, fontWeight: "700", color: theme.text, flex: 1 },
    itemMastered: { color: theme.textSecondary, textDecorationLine: "line-through" },
    itemDef: { fontSize: 14, color: theme.textSecondary },
    itemNote: { fontSize: 13, lineHeight: 18, color: theme.textSecondary, fontStyle: "italic" },
    itemMeta: { fontSize: 11, fontWeight: "600", color: theme.textTertiary, marginTop: 2 },
    comingSoon: {
      backgroundColor: theme.surface,
      borderRadius: 16,
      padding: 16,
      gap: 8,
    },
    comingSoonTitle: { fontSize: 16, fontWeight: "700", color: theme.text },
    comingSoonBody: { fontSize: 14, lineHeight: 21, color: theme.textSecondary },
    practiceSection: {
      backgroundColor: theme.surface,
      borderRadius: 16,
      padding: 16,
      gap: 10,
    },
    practiceTitle: { fontSize: 16, fontWeight: "700", color: theme.text },
    practiceBody: { fontSize: 14, lineHeight: 21, color: theme.textSecondary },
    deleteBtn: { alignItems: "center", paddingVertical: 10 },
    deleteBtnText: { fontSize: 15, fontWeight: "600", color: theme.danger },
  });
}
