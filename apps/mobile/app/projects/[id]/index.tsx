import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useFocusEffect, useLocalSearchParams, useNavigation, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { ProjectDailyStrip } from "@/components/ProjectDailyStrip";
import { ProjectDayItemsList, type ProjectStudyAction } from "@/components/ProjectDayItemsList";
import { ProjectProgressHero, type ProjectDaySnapshot } from "@/components/ProjectProgressHero";
import { ProjectItemRow } from "@/components/ProjectItemRow";
import { LearningContinueCta } from "@/components/projects/LearningContinueCta";
import { useAuth } from "@/contexts/AuthContext";
import { api, type ProjectDetail, type VocabStatus } from "@/lib/api";
import { queueChatLaunch } from "@/lib/chatLaunch";
import {
  exportProjectAsPdf,
  projectHasExportableItems,
} from "@/lib/exportProjectPdf";
import { isShareCancelled } from "@/lib/exportPdf";
import {
  buildProjectAskPromptFromProject,
  buildProjectBonusQuestionsPrompt,
  buildProjectBonusWordsPrompt,
  buildProjectReviewPrompt,
  isDailyGoalMet,
  remainingDailyGoal,
} from "@/lib/projectChat";
import {
  fetchProjectDetail,
  getCachedProjectDetail,
  invalidateProjectDetail,
  isProjectDetailFresh,
} from "@/lib/projectDetailCache";
import { isLanguageProject } from "@/lib/languageLevels";
import { resolveDailyGoal } from "@/lib/dailyGoals";
import { localDateKey } from "@/lib/reminderCalendar";
import {
  formatProjectListTitle,
  isConceptProject,
  isTriviaProject,
  learningProjectTitle,
  projectStatsLabels,
} from "@/lib/projectUi";
import { Theme, useTheme } from "@/lib/theme";
import { weekdayFullLabel } from "@/lib/weekdayLabels";

export default function ProjectDetailScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const router = useRouter();
  const navigation = useNavigation();
  const { id } = useLocalSearchParams<{ id: string }>();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const initialProject =
    typeof id === "string" ? getCachedProjectDetail(id) ?? null : null;
  const [loading, setLoading] = useState(!initialProject);
  const [loadError, setLoadError] = useState(false);
  const [project, setProject] = useState<ProjectDetail | null>(initialProject);
  const hasLoadedRef = useRef(Boolean(initialProject));
  const projectRef = useRef(project);
  projectRef.current = project;
  const [selectedDay, setSelectedDay] = useState(() => localDateKey(new Date()));
  const [conceptBusyId, setConceptBusyId] = useState<string | null>(null);
  const [exportingPdf, setExportingPdf] = useState(false);

  const load = useCallback(
    async (opts?: { silent?: boolean; force?: boolean }) => {
      if (!token || typeof id !== "string") return;
      const firstLoad = !hasLoadedRef.current;
      if (!opts?.silent && firstLoad && !projectRef.current) setLoading(true);
      setLoadError(false);
      try {
        const data = await fetchProjectDetail(token, id, { force: opts?.force });
        if (data) {
          setProject(data);
        } else if (!projectRef.current) {
          setProject(null);
          setLoadError(true);
        }
      } catch {
        if (!projectRef.current) {
          setProject(null);
          setLoadError(true);
        }
      } finally {
        hasLoadedRef.current = true;
        if (!opts?.silent && firstLoad) setLoading(false);
      }
    },
    [token, id, router],
  );

  useFocusEffect(
    useCallback(() => {
      if (typeof id !== "string") return;
      const cached = getCachedProjectDetail(id);
      const hasPaint = Boolean(projectRef.current || cached);
      const fresh = isProjectDetailFresh(id);
      // Paint cache immediately; only force-network when stale/missing so quiz
      // returns still refresh after invalidateProjectDetail.
      void load({ silent: hasPaint, force: !fresh });
    }, [load, id]),
  );

  const exportLearningPdf = useCallback(async () => {
    if (!token || !project || exportingPdf) return;
    if (!projectHasExportableItems(project)) {
      Alert.alert(t("projects.export_pdf_empty_title"), t("projects.export_pdf_empty_body"));
      return;
    }
    setExportingPdf(true);
    try {
      const withLists = await api.getProject(token, project.id, { includeLists: true });
      await exportProjectAsPdf(withLists, {
        mastered: t("projects.export_pdf.section_mastered"),
        learning: t("projects.export_pdf.section_learning"),
        new: t("projects.export_pdf.section_new"),
        empty: t("projects.export_pdf.empty"),
        definition: t("projects.export_pdf.definition"),
        example: t("projects.export_pdf.example"),
        topic: t("projects.export_pdf.topic"),
        summary: ({ total, mastered, learning, newCount }) =>
          t("projects.export_pdf.summary", {
            total,
            mastered,
            learning,
            new: newCount,
          }),
      });
    } catch (error) {
      if (isShareCancelled(error)) return;
      Alert.alert(t("common.error"), t("projects.export_pdf_failed"));
    } finally {
      setExportingPdf(false);
    }
  }, [token, project, exportingPdf, t]);

  useLayoutEffect(() => {
    if (!project) return;
    navigation.setOptions({
      title: learningProjectTitle(project.kind, t, project.title),
      headerRight: () => (
        <Pressable
          onPress={() => void exportLearningPdf()}
          disabled={exportingPdf}
          hitSlop={8}
          accessibilityLabel={t("projects.export_pdf_a11y")}
          style={{ marginRight: 4, opacity: exportingPdf ? 0.45 : 1 }}
        >
          {exportingPdf ? (
            <ActivityIndicator size="small" color={theme.primary} />
          ) : (
            <Ionicons name="document-text-outline" size={22} color={theme.primary} />
          )}
        </Pressable>
      ),
    });
  }, [navigation, project, t, exportLearningPdf, exportingPdf, theme.primary]);

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
            invalidateProjectDetail(project.id);
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
  const showDailyStudyCta =
    isToday &&
    (isLang || isTrivia) &&
    dailyGoal != null &&
    !dailyGoalMet &&
    remainingToday > 0;
  const showReviewCta = isToday && dailyGoalMet && stats.due_for_review > 0;
  const selectedDayMissed = project.daily_missed_by_date?.[selectedDay] ?? [];
  const daySnapshotTitle = isToday
    ? t("projects.stats.today")
    : weekdayFullLabel(selectedDayMeta?.weekday ?? 0, t).toUpperCase();
  const daySnapshot: ProjectDaySnapshot | null =
    showDailyTracking && dailyGoal && selectedDayMeta
      ? {
          title: daySnapshotTitle,
          masteredCount: selectedDayMeta.mastered_count,
          missedCount: selectedDayMeta.missed_count ?? 0,
          dailyGoal: selectedDayMeta.daily_goal,
          isToday,
        }
      : null;

  const dailyStudyCtaLabel =
    stats.mastered_today === 0 && (stats.missed_today ?? 0) === 0
      ? isTrivia
        ? t("projects.study.start_questions")
        : t("projects.study.start_words", { count: dailyGoal })
      : isTrivia
        ? t("projects.list.continue_questions", { count: remainingToday })
        : t("projects.list.continue_words", { count: remainingToday });

  const handleItemStatusChange = async (itemId: string, status: VocabStatus) => {
    if (!token || typeof id !== "string") return;
    setConceptBusyId(itemId);
    try {
      await api.updateProjectItem(token, id, itemId, { status });
      await load({ silent: true, force: true });
    } catch {
      Alert.alert(t("common.error"), t("projects.status_update_failed"));
    } finally {
      setConceptBusyId(null);
    }
  };

  const startReviewSession = () => {
    const variant = isTrivia ? "trivia" : isLang ? "vocab" : undefined;
    invalidateProjectDetail(project.id);
    queueChatLaunch(
      buildProjectReviewPrompt(project),
      project.id,
      isLang ? "en" : undefined,
      variant,
      "chat",
    );
    router.replace("/");
  };

  const startStudyQuiz = () => {
    const variant = isTrivia ? "trivia" : isLang ? "vocab" : undefined;
    invalidateProjectDetail(project.id);
    queueChatLaunch(
      buildProjectAskPromptFromProject(project, t),
      project.id,
      isLang ? "en" : undefined,
      variant,
      "chat",
    );
    router.replace("/");
  };

  const startStudyBonus = () => {
    invalidateProjectDetail(project.id);
    if (isTrivia) {
      queueChatLaunch(buildProjectBonusQuestionsPrompt(project), project.id, undefined, "trivia", "chat");
    } else if (isLang) {
      queueChatLaunch(buildProjectBonusWordsPrompt(project), project.id, "en");
    }
    router.replace("/");
  };

  // List-footer CTA only when it's a different action than the primary filled
  // button under TODAY (bonus after goal). Start/continue live on the primary CTA.
  let todayStudyAction: ProjectStudyAction | null = null;
  if ((isLang || isTrivia) && dailyGoal && isToday && dailyGoalMet) {
    todayStudyAction = {
      label: isTrivia ? t("projects.add_bonus_questions") : t("projects.add_bonus_words"),
      onPress: startStudyBonus,
    };
  }

  return (
    <>
    <ScrollView style={s.root} contentContainerStyle={s.content}>
      {isConcept ? (
        <View style={s.hero}>
          <Text style={s.title}>{project.title}</Text>
          {project.description ? (
            <Text style={s.description}>{project.description}</Text>
          ) : null}
        </View>
      ) : null}

      {showDailyTracking ? (
        <ProjectDailyStrip
          days={project.daily_history ?? []}
          selectedDate={selectedDay}
          onSelectDate={setSelectedDay}
        />
      ) : null}

      <ProjectProgressHero
        stats={stats}
        learnedLabel={statLabels.learned}
        todayLearnedLabel={statLabels.learnedToday}
        dueLabel={statLabels.due}
        dailyGoal={dailyGoal}
        daySnapshot={daySnapshot}
        streakDays={stats.streak_days}
        daysInactive={stats.days_inactive}
      />

      {showDailyStudyCta ? (
        <View style={showDailyTracking ? s.studyCtaBeforeList : undefined}>
          <LearningContinueCta label={dailyStudyCtaLabel} onPress={startStudyQuiz} />
        </View>
      ) : showReviewCta ? (
        <View style={showDailyTracking ? s.studyCtaBeforeList : undefined}>
          <LearningContinueCta
            label={
              isTrivia
                ? t("projects.list.review_facts", { count: stats.due_for_review })
                : t("projects.list.review_words", { count: stats.due_for_review })
            }
            onPress={startReviewSession}
          />
        </View>
      ) : null}

      {showDailyTracking && token ? (
        <ProjectDayItemsList
          token={token}
          projectId={project.id}
          activityDate={selectedDay}
          dayMeta={selectedDayMeta}
          isTrivia={isTrivia}
          itemsByDate={project.daily_items_by_date ?? {}}
          missedItems={selectedDayMissed}
          studyAction={todayStudyAction}
          onItemUpdated={() => load({ silent: true, force: true })}
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
                    onStatusChange={(status) => handleItemStatusChange(item.id, status)}
                  />
                ))}
              </View>
            ))
          ) : (
            <View style={s.comingSoon}>
              <Text style={s.comingSoonBody}>
                {t("projects.concept_empty")}
              </Text>
            </View>
          )}
        </>
      ) : null}

      <Pressable style={s.deleteBtn} onPress={confirmDelete}>
        <Text style={s.deleteBtnText}>{t("projects.delete")}</Text>
      </Pressable>
    </ScrollView>
    </>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: theme.bg },
    center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.bg },
    content: { padding: 16, gap: 16, paddingBottom: 40 },
    studyCtaBeforeList: { marginBottom: 8 },
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
