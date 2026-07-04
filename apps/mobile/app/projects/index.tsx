import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { useProjects } from "@/contexts/ProjectsContext";
import { api, type LanguageLevel, type ProjectKind } from "@/lib/api";
import { LANGUAGE_LEVELS, levelLabel } from "@/lib/languageLevels";
import { findLanguageProject } from "@/lib/languageProject";
import { queueChatLaunch } from "@/lib/chatLaunch";
import { buildEnglishOnboardingPrompt, buildTriviaOnboardingPrompt } from "@/lib/projectChat";
import {
  englishProjectTitle,
  triviaProjectTitle,
  type CreateStep,
} from "@/lib/projectCreateFlow";
import { findTriviaProject } from "@/lib/triviaProject";
import {
  encodeTriviaTopics,
  formatTriviaTopicLabels,
  TRIVIA_TOPICS,
  type TriviaTopicId,
} from "@/lib/triviaTopics";
import {
  DEFAULT_VOCAB_DAILY_GOAL,
  VOCAB_DAILY_GOALS,
  type VocabDailyGoal,
} from "@/lib/dailyGoals";
import { Theme, useTheme } from "@/lib/theme";

const SUBJECTS: ProjectKind[] = ["language", "trivia"];

function kindIcon(kind: ProjectKind): keyof typeof Ionicons.glyphMap {
  if (kind === "language" || kind === "vocabulary") return "language-outline";
  if (kind === "trivia") return "bulb-outline";
  return "folder-outline";
}

function projectRowMeta(
  project: { kind: ProjectKind; level: LanguageLevel; target_language: string; description: string | null },
  t: (key: string, opts?: Record<string, unknown>) => string,
): string {
  const kindKey = project.kind === "vocabulary" ? "language" : project.kind;
  if (project.kind === "language" || project.kind === "vocabulary") {
    return `${t(`projects.kind.${kindKey}`)} · ${levelLabel(project.level)}`;
  }
  if (project.kind === "trivia") {
    const topics = project.description?.split(",").filter(Boolean).length ?? 0;
    return `${t("projects.kind.trivia")} · ${t("projects.trivia.topic_count", { count: topics })}`;
  }
  return t(`projects.kind.${kindKey}`);
}

export default function ProjectsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { projects, loading, error, refresh, setProjects } = useProjects();
  const visibleProjects = useMemo(
    () => projects.filter((project) => project.kind !== "programming"),
    [projects],
  );
  const [createStep, setCreateStep] = useState<CreateStep | null>(null);
  const [kind, setKind] = useState<ProjectKind | null>(null);
  const [level, setLevel] = useState<LanguageLevel>("level1");
  const [dailyGoal, setDailyGoal] = useState<VocabDailyGoal>(DEFAULT_VOCAB_DAILY_GOAL);
  const [triviaTopics, setTriviaTopics] = useState<TriviaTopicId[]>(["history", "science"]);
  const [creating, setCreating] = useState(false);

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: projects.length > 0 });
    }, [refresh, projects.length]),
  );

  if (!token) return <Redirect href="/login" />;

  const resetCreate = () => {
    setCreateStep(null);
    setKind(null);
    setLevel("level1");
    setDailyGoal(DEFAULT_VOCAB_DAILY_GOAL);
    setTriviaTopics(["history", "science"]);
    setCreating(false);
  };

  const openCreate = () => {
    resetCreate();
    setCreateStep("subject");
  };

  const selectSubject = (next: ProjectKind) => {
    if (next === "language") {
      const existing = findLanguageProject(projects, "en");
      if (existing) {
        resetCreate();
        router.push(`/projects/${existing.id}`);
        return;
      }
      setKind(next);
      setCreateStep("level");
      return;
    }
    if (next === "trivia") {
      const existing = findTriviaProject(projects);
      if (existing) {
        resetCreate();
        router.push(`/projects/${existing.id}`);
        return;
      }
      setKind(next);
      setCreateStep("topics");
    }
  };

  const handleCreateEnglish = async () => {
    if (!token || kind !== "language" || creating) return;

    const title = englishProjectTitle(level, t);

    setCreating(true);
    try {
      const project = await api.createProject(token, {
        title,
        description: "",
        kind: "language",
        level,
        target_language: "en",
        daily_goal: dailyGoal,
      });
      resetCreate();
      setProjects((prev) => [project, ...prev]);
      queueChatLaunch(buildEnglishOnboardingPrompt(title, level, dailyGoal), project.id, "en");
      router.replace("/");
    } catch {
      Alert.alert(t("common.error"), t("projects.create_failed"));
    } finally {
      setCreating(false);
    }
  };

  const handleCreateTrivia = async () => {
    if (!token || kind !== "trivia" || creating || triviaTopics.length === 0) return;

    const title = triviaProjectTitle(t);
    const description = encodeTriviaTopics(triviaTopics);
    const topicLabels = formatTriviaTopicLabels(triviaTopics, t);

    setCreating(true);
    try {
      const project = await api.createProject(token, {
        title,
        description,
        kind: "trivia",
        level: "level1",
        target_language: "en",
        daily_goal: dailyGoal,
      });
      resetCreate();
      setProjects((prev) => [project, ...prev]);
      queueChatLaunch(buildTriviaOnboardingPrompt(topicLabels, dailyGoal), project.id, undefined, "trivia");
      router.replace("/");
    } catch {
      Alert.alert(t("common.error"), t("projects.create_failed"));
    } finally {
      setCreating(false);
    }
  };

  const toggleTriviaTopic = (topicId: TriviaTopicId) => {
    setTriviaTopics((prev) => {
      if (prev.includes(topicId)) {
        const next = prev.filter((id) => id !== topicId);
        return next.length > 0 ? next : prev;
      }
      return [...prev, topicId];
    });
  };

  const renderCreateSteps = () => {
    if (!createStep) return null;

    return (
      <>
        {createStep === "subject" ? (
          <>
            <Text style={s.createLabel}>{t("projects.what_to_learn")}</Text>
            <View style={s.subjectList}>
              {SUBJECTS.map((item) => {
                const existingEnglish =
                  item === "language" ? findLanguageProject(projects, "en") : undefined;
                const existingTrivia = item === "trivia" ? findTriviaProject(projects) : undefined;
                const continueHint =
                  existingEnglish && item === "language"
                    ? t("projects.language_continue")
                    : existingTrivia && item === "trivia"
                      ? t("projects.trivia_continue")
                      : null;
                return (
                  <Pressable
                    key={item}
                    style={s.subjectRow}
                    onPress={() => selectSubject(item)}
                  >
                    <View style={s.subjectIcon}>
                      <Ionicons name={kindIcon(item)} size={22} color={C.primary} />
                    </View>
                    <View style={s.subjectMain}>
                      <Text style={s.subjectText}>{t(`projects.kind.${item}`)}</Text>
                      {continueHint ? (
                        <Text style={s.subjectHint}>{continueHint}</Text>
                      ) : null}
                    </View>
                    <Ionicons name="chevron-forward" size={18} color={C.textTertiary} />
                  </Pressable>
                );
              })}
            </View>
          </>
        ) : null}

        {createStep === "level" ? (
          <>
            <Text style={s.createLabel}>{t("projects.level_label")}</Text>
            <Text style={s.stepHint}>{t("projects.level_hint")}</Text>
            <View style={s.subjectList}>
              {LANGUAGE_LEVELS.map((item) => (
                <Pressable
                  key={item}
                  style={[s.subjectRow, level === item && s.subjectRowActive]}
                  onPress={() => setLevel(item)}
                >
                  <Text style={[s.subjectText, level === item && s.subjectTextActive]}>
                    {levelLabel(item)}
                  </Text>
                  {level === item ? (
                    <Ionicons name="checkmark" size={18} color={C.primary} />
                  ) : null}
                </Pressable>
              ))}
            </View>
            <View style={s.createActions}>
              <Pressable style={s.secondaryBtn} onPress={() => setCreateStep("subject")}>
                <Text style={s.secondaryBtnText}>{t("projects.back")}</Text>
              </Pressable>
              <Pressable style={s.primaryBtn} onPress={() => setCreateStep("daily")}>
                <Text style={s.primaryBtnText}>{t("common.continue")}</Text>
              </Pressable>
            </View>
          </>
        ) : null}

        {createStep === "topics" ? (
          <>
            <Text style={s.createLabel}>{t("projects.trivia.topics_label")}</Text>
            <Text style={s.stepHint}>{t("projects.trivia.topics_hint")}</Text>
            <View style={s.subjectList}>
              {TRIVIA_TOPICS.map((topic) => {
                const selected = triviaTopics.includes(topic.id);
                return (
                  <Pressable
                    key={topic.id}
                    style={[s.subjectRow, selected && s.subjectRowActive]}
                    onPress={() => toggleTriviaTopic(topic.id)}
                  >
                    <Text style={[s.subjectText, selected && s.subjectTextActive]}>
                      {t(topic.labelKey)}
                    </Text>
                    {selected ? (
                      <Ionicons name="checkmark" size={18} color={C.primary} />
                    ) : null}
                  </Pressable>
                );
              })}
            </View>
            <View style={s.createActions}>
              <Pressable style={s.secondaryBtn} onPress={() => setCreateStep("subject")}>
                <Text style={s.secondaryBtnText}>{t("projects.back")}</Text>
              </Pressable>
              <Pressable style={s.primaryBtn} onPress={() => setCreateStep("daily")}>
                <Text style={s.primaryBtnText}>{t("common.continue")}</Text>
              </Pressable>
            </View>
          </>
        ) : null}

        {createStep === "daily" ? (
          <>
            <Text style={s.createLabel}>
              {kind === "trivia"
                ? t("projects.trivia.daily_label")
                : t("projects.daily_goal_label")}
            </Text>
            <Text style={s.stepHint}>
              {kind === "trivia" ? t("projects.trivia.daily_hint") : t("projects.daily_goal_hint")}
            </Text>
            <View style={s.subjectList}>
              {VOCAB_DAILY_GOALS.map((item) => (
                <Pressable
                  key={item}
                  style={[s.subjectRow, dailyGoal === item && s.subjectRowActive]}
                  onPress={() => setDailyGoal(item)}
                >
                  <Text style={[s.subjectText, dailyGoal === item && s.subjectTextActive]}>
                    {kind === "trivia"
                      ? t("projects.trivia.daily_questions", { count: item })
                      : t("projects.daily_goal_words", { count: item })}
                  </Text>
                  {dailyGoal === item ? (
                    <Ionicons name="checkmark" size={18} color={C.primary} />
                  ) : null}
                </Pressable>
              ))}
            </View>
            <View style={s.createActions}>
              <Pressable
                style={s.secondaryBtn}
                onPress={() => setCreateStep(kind === "trivia" ? "topics" : "level")}
              >
                <Text style={s.secondaryBtnText}>{t("projects.back")}</Text>
              </Pressable>
              <Pressable
                style={[s.primaryBtn, creating && s.primaryBtnDisabled]}
                disabled={creating}
                onPress={() =>
                  void (kind === "trivia" ? handleCreateTrivia() : handleCreateEnglish())
                }
              >
                {creating ? (
                  <ActivityIndicator color={C.onPrimary} />
                ) : (
                  <Text style={s.primaryBtnText}>{t("projects.create")}</Text>
                )}
              </Pressable>
            </View>
          </>
        ) : null}
      </>
    );
  };

  return (
    <View style={s.root}>
      {loading ? (
        <View style={s.center}>
          <ActivityIndicator color={C.primary} />
        </View>
      ) : (
        <ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
          <Pressable style={s.newProjectBtn} onPress={openCreate}>
            <Ionicons name="add-circle-outline" size={22} color={C.primary} />
            <Text style={s.newProjectText}>{t("projects.add_learning")}</Text>
          </Pressable>

          {!error && visibleProjects.length === 0 ? (
            <View style={s.emptyState}>
              <Text style={s.emptyTitle}>{t("projects.empty_title")}</Text>
              <Text style={s.emptyBody}>{t("projects.empty_body")}</Text>
            </View>
          ) : null}

          {error ? (
            <Text style={s.empty}>{t("common.error")}</Text>
          ) : (
            visibleProjects.map((project) => (
              <Pressable
                key={project.id}
                style={s.row}
                onPress={() => router.push(`/projects/${project.id}`)}
              >
                <View style={s.rowIcon}>
                  <Ionicons name={kindIcon(project.kind)} size={20} color={C.primary} />
                </View>
                <View style={s.rowMain}>
                  <Text style={s.rowTitle} numberOfLines={1}>
                    {project.title}
                  </Text>
                  <Text style={s.rowMeta} numberOfLines={1}>
                    {projectRowMeta(project, t)}
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={C.textTertiary} />
              </Pressable>
            ))
          )}
        </ScrollView>
      )}

      <Modal
        visible={createStep !== null}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={resetCreate}
      >
        <KeyboardAvoidingView
          style={[s.modalRoot, { paddingTop: insets.top }]}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          <View style={s.modalHeader}>
            <Pressable style={s.modalClose} onPress={resetCreate} hitSlop={8}>
              <Ionicons name="close" size={26} color={C.textSecondary} />
            </Pressable>
            <Text style={s.modalHeaderTitle}>{t("projects.add_learning")}</Text>
            <View style={s.modalClose} />
          </View>
          <ScrollView
            contentContainerStyle={[s.modalContent, { paddingBottom: insets.bottom + 24 }]}
            keyboardShouldPersistTaps="handled"
          >
            <View style={s.createCard}>{renderCreateSteps()}</View>
          </ScrollView>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    center: { flex: 1, alignItems: "center", justifyContent: "center" },
    content: { padding: 16, gap: 12, paddingBottom: 32 },
    newProjectBtn: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingVertical: 14,
      paddingHorizontal: 14,
      borderRadius: 14,
      backgroundColor: C.primaryLight,
    },
    newProjectText: { fontSize: 16, fontWeight: "700", color: C.primary },
    emptyState: {
      backgroundColor: C.surface,
      borderRadius: 16,
      padding: 20,
      gap: 8,
      alignItems: "center",
    },
    emptyTitle: { fontSize: 17, fontWeight: "700", color: C.text, textAlign: "center" },
    emptyBody: { fontSize: 15, lineHeight: 22, color: C.textSecondary, textAlign: "center" },
    modalRoot: { flex: 1, backgroundColor: C.bg },
    modalHeader: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 12,
      paddingVertical: 10,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: C.border,
    },
    modalClose: { width: 40, alignItems: "center", justifyContent: "center" },
    modalHeaderTitle: {
      flex: 1,
      textAlign: "center",
      fontSize: 17,
      fontWeight: "700",
      color: C.text,
    },
    modalContent: { padding: 16 },
    createCard: { gap: 10 },
    createLabel: { fontSize: 20, fontWeight: "700", color: C.text },
    stepHint: { fontSize: 14, color: C.textSecondary, marginBottom: 4 },
    subjectList: { gap: 8 },
    subjectRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingVertical: 14,
      paddingHorizontal: 12,
      borderRadius: 14,
      backgroundColor: C.surface,
      borderWidth: 1,
      borderColor: C.border,
    },
    subjectRowActive: {
      borderColor: C.primary,
      backgroundColor: C.primaryLight,
    },
    subjectIcon: {
      width: 40,
      height: 40,
      borderRadius: 12,
      backgroundColor: C.bg,
      alignItems: "center",
      justifyContent: "center",
    },
    subjectText: { fontSize: 16, fontWeight: "600", color: C.text },
    subjectMain: { flex: 1, gap: 2 },
    subjectHint: { fontSize: 13, color: C.textSecondary },
    subjectRowMuted: { opacity: 0.65 },
    subjectTextActive: { color: C.primaryDark },
    input: {
      backgroundColor: C.surface,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: C.border,
      paddingHorizontal: 12,
      paddingVertical: 10,
      fontSize: 16,
      color: C.text,
    },
    inputMultiline: { minHeight: 88, textAlignVertical: "top" },
    createActions: { flexDirection: "row", gap: 10, marginTop: 8 },
    secondaryBtn: {
      flex: 1,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: C.border,
      paddingVertical: 12,
      alignItems: "center",
    },
    secondaryBtnText: { fontSize: 15, fontWeight: "600", color: C.textSecondary },
    primaryBtn: {
      flex: 1,
      borderRadius: 12,
      backgroundColor: C.primary,
      paddingVertical: 12,
      alignItems: "center",
      justifyContent: "center",
      minHeight: 46,
    },
    primaryBtnDisabled: { opacity: 0.45 },
    primaryBtnText: { fontSize: 15, fontWeight: "700", color: C.onPrimary },
    empty: {
      textAlign: "center",
      color: C.textSecondary,
      fontSize: 15,
      paddingVertical: 24,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingVertical: 14,
      paddingHorizontal: 12,
      borderRadius: 14,
      backgroundColor: C.surface,
    },
    rowIcon: {
      width: 40,
      height: 40,
      borderRadius: 12,
      backgroundColor: C.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    rowMain: { flex: 1, gap: 2 },
    rowTitle: { fontSize: 16, fontWeight: "700", color: C.text },
    rowMeta: { fontSize: 13, color: C.textSecondary },
    fieldLabel: {
      fontSize: 14,
      fontWeight: "600",
      color: C.textSecondary,
      marginTop: 4,
    },
  });
}
