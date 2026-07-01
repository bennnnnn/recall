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
  TextInput,
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
import {
  ENGLISH_LEARNING_TOPICS,
  englishTopicLabel,
  englishTopicsDescription,
  sortEnglishTopics,
  type EnglishLearningTopicId,
} from "@/lib/englishLearningTopics";
import { queueChatLaunch } from "@/lib/chatLaunch";
import { buildEnglishOnboardingPrompt } from "@/lib/projectChat";
import {
  englishProjectTitle,
  goalPlaceholderKey,
  goalStepHint,
  resolveProjectDescription,
  resolveProjectTitle,
  titlePlaceholderKey,
  type CreateStep,
} from "@/lib/projectCreateFlow";
import {
  PROGRAMMING_LANGUAGES,
  programmingLanguageLabel,
  type ProgrammingLanguageId,
} from "@/lib/programmingLanguages";
import { Theme, useTheme } from "@/lib/theme";

const SUBJECTS: ProjectKind[] = ["language", "math", "programming"];

function kindIcon(kind: ProjectKind): keyof typeof Ionicons.glyphMap {
  if (kind === "language" || kind === "vocabulary") return "language-outline";
  if (kind === "programming") return "code-slash-outline";
  if (kind === "math") return "calculator-outline";
  return "folder-outline";
}

function projectRowMeta(
  project: { kind: ProjectKind; level: LanguageLevel; target_language: string },
  t: (key: string, opts?: Record<string, unknown>) => string,
): string {
  const kindKey = project.kind === "vocabulary" ? "language" : project.kind;
  if (project.kind === "language" || project.kind === "vocabulary") {
    return `${t(`projects.kind.${kindKey}`)} · ${levelLabel(project.level)}`;
  }
  if (project.kind === "programming") {
    return `${programmingLanguageLabel(project.target_language)} · ${t("projects.kind.programming")}`;
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
  const [createStep, setCreateStep] = useState<CreateStep | null>(null);
  const [titleInput, setTitleInput] = useState("");
  const [goalInput, setGoalInput] = useState("");
  const [kind, setKind] = useState<ProjectKind | null>(null);
  const [level, setLevel] = useState<LanguageLevel>("level1");
  const [programmingLanguage, setProgrammingLanguage] = useState<ProgrammingLanguageId | null>(
    null,
  );
  const [englishTopics, setEnglishTopics] = useState<EnglishLearningTopicId[]>([]);
  const [creating, setCreating] = useState(false);

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: projects.length > 0 });
    }, [refresh, projects.length]),
  );

  if (!token) return <Redirect href="/login" />;

  const resetCreate = () => {
    setCreateStep(null);
    setTitleInput("");
    setGoalInput("");
    setKind(null);
    setLevel("level1");
    setProgrammingLanguage(null);
    setEnglishTopics([]);
    setCreating(false);
  };

  const openCreate = () => {
    resetCreate();
    setCreateStep("subject");
  };

  const selectSubject = (next: ProjectKind) => {
    setKind(next);
    if (next === "language") setCreateStep("level");
    else if (next === "programming") {
      setProgrammingLanguage(null);
      setCreateStep("stack");
    } else setCreateStep("goal");
  };

  const selectProgrammingLanguage = (lang: ProgrammingLanguageId) => {
    setProgrammingLanguage(lang);
    setCreateStep("goal");
  };

  const goalBackStep = (): CreateStep => {
    if (kind === "language") return "level";
    if (kind === "programming") return "stack";
    return "subject";
  };

  const toggleEnglishTopic = (topicId: EnglishLearningTopicId) => {
    setEnglishTopics((prev) =>
      prev.includes(topicId) ? prev.filter((id) => id !== topicId) : [...prev, topicId],
    );
  };

  const handleCreateEnglish = async () => {
    if (!token || kind !== "language" || creating || englishTopics.length === 0) return;

    const sortedTopics = sortEnglishTopics(englishTopics);
    const title = englishProjectTitle(level, t);
    const description = englishTopicsDescription(sortedTopics, t);
    const focusLabels = sortedTopics.map((id) => englishTopicLabel(id, t));

    setCreating(true);
    try {
      const project = await api.createProject(token, {
        title,
        description,
        kind: "language",
        level,
        target_language: "en",
      });
      resetCreate();
      setProjects((prev) => [project, ...prev]);
      queueChatLaunch(buildEnglishOnboardingPrompt(title, level, focusLabels), project.id, "en");
      router.replace("/");
    } catch {
      Alert.alert(t("common.error"), t("projects.create_failed"));
    } finally {
      setCreating(false);
    }
  };

  const handleCreate = async () => {
    if (!token || !kind || creating) return;
    const title = resolveProjectTitle(titleInput, kind, level, programmingLanguage, t);
    if (!title.trim()) return;
    if (kind === "programming" && !programmingLanguage) return;

    setCreating(true);
    try {
      const project = await api.createProject(token, {
        title,
        description: resolveProjectDescription(titleInput, goalInput),
        kind,
        level,
        target_language: kind === "programming" ? programmingLanguage! : "en",
      });
      resetCreate();
      setProjects((prev) => [project, ...prev]);
      router.push(`/projects/${project.id}`);
    } catch {
      Alert.alert(t("common.error"), t("projects.create_failed"));
    } finally {
      setCreating(false);
    }
  };

  const canCreateEnglish = englishTopics.length > 0 && !creating;
  const canCreate = titleInput.trim().length > 0 && !creating;

  const renderCreateSteps = () => {
    if (!createStep) return null;

    return (
      <>
        {createStep === "subject" ? (
          <>
            <Text style={s.createLabel}>{t("projects.what_to_learn")}</Text>
            <View style={s.subjectList}>
              {SUBJECTS.map((item) => (
                <Pressable
                  key={item}
                  style={s.subjectRow}
                  onPress={() => selectSubject(item)}
                >
                  <View style={s.subjectIcon}>
                    <Ionicons name={kindIcon(item)} size={22} color={C.primary} />
                  </View>
                  <Text style={s.subjectText}>{t(`projects.kind.${item}`)}</Text>
                  <Ionicons name="chevron-forward" size={18} color={C.textTertiary} />
                </Pressable>
              ))}
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
                  <Text
                    style={[s.subjectText, level === item && s.subjectTextActive]}
                  >
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
              <Pressable style={s.primaryBtn} onPress={() => setCreateStep("topics")}>
                <Text style={s.primaryBtnText}>{t("projects.next")}</Text>
              </Pressable>
            </View>
          </>
        ) : null}

        {createStep === "topics" && kind === "language" ? (
          <>
            <Text style={s.createLabel}>{t("projects.english_topics_label")}</Text>
            <Text style={s.stepHint}>{t("projects.english_topics_hint")}</Text>
            <Text style={s.stepHint}>{goalStepHint(kind, level, programmingLanguage, t)}</Text>
            <View style={s.subjectList}>
              {ENGLISH_LEARNING_TOPICS.map((topic) => {
                const selected = englishTopics.includes(topic.id);
                return (
                  <Pressable
                    key={topic.id}
                    style={[s.subjectRow, selected && s.subjectRowActive]}
                    onPress={() => toggleEnglishTopic(topic.id)}
                  >
                    <View style={s.subjectIcon}>
                      <Ionicons name={topic.icon} size={22} color={C.primary} />
                    </View>
                    <Text style={[s.subjectText, selected && s.subjectTextActive]}>
                      {englishTopicLabel(topic.id, t)}
                    </Text>
                    {selected ? (
                      <Ionicons name="checkmark" size={18} color={C.primary} />
                    ) : null}
                  </Pressable>
                );
              })}
            </View>
            <View style={s.createActions}>
              <Pressable style={s.secondaryBtn} onPress={() => setCreateStep("level")}>
                <Text style={s.secondaryBtnText}>{t("projects.back")}</Text>
              </Pressable>
              <Pressable
                style={[s.primaryBtn, !canCreateEnglish && s.primaryBtnDisabled]}
                disabled={!canCreateEnglish}
                onPress={() => void handleCreateEnglish()}
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

        {createStep === "stack" ? (
          <>
            <Text style={s.createLabel}>{t("projects.pick_programming_language")}</Text>
            <Text style={s.stepHint}>{t("projects.programming_language_hint")}</Text>
            <View style={s.subjectList}>
              {PROGRAMMING_LANGUAGES.map((lang) => (
                <Pressable
                  key={lang.id}
                  style={[
                    s.subjectRow,
                    programmingLanguage === lang.id && s.subjectRowActive,
                  ]}
                  onPress={() => selectProgrammingLanguage(lang.id)}
                >
                  <View style={s.subjectIcon}>
                    <Ionicons name="code-slash-outline" size={22} color={C.primary} />
                  </View>
                  <Text
                    style={[
                      s.subjectText,
                      programmingLanguage === lang.id && s.subjectTextActive,
                    ]}
                  >
                    {lang.label}
                  </Text>
                  <Ionicons name="chevron-forward" size={18} color={C.textTertiary} />
                </Pressable>
              ))}
            </View>
            <Pressable style={s.secondaryBtn} onPress={() => setCreateStep("subject")}>
              <Text style={s.secondaryBtnText}>{t("projects.back")}</Text>
            </Pressable>
          </>
        ) : null}

        {createStep === "goal" && kind && kind !== "language" ? (
          <>
            <Text style={s.createLabel}>{t("projects.step_goal")}</Text>
            <Text style={s.stepHint}>
              {goalStepHint(kind, level, programmingLanguage, t)}
            </Text>
            <Text style={s.fieldLabel}>{t("projects.title_label")}</Text>
            <TextInput
              style={s.input}
              placeholder={t(titlePlaceholderKey(kind))}
              placeholderTextColor={C.textTertiary}
              value={titleInput}
              onChangeText={setTitleInput}
              autoFocus
              maxLength={80}
              returnKeyType="next"
            />
            <Text style={s.fieldLabel}>{t("projects.goal_optional_hint")}</Text>
            <TextInput
              style={[s.input, s.inputMultiline]}
              placeholder={t(goalPlaceholderKey(kind))}
              placeholderTextColor={C.textTertiary}
              value={goalInput}
              onChangeText={setGoalInput}
              multiline
            />
            <View style={s.createActions}>
              <Pressable style={s.secondaryBtn} onPress={() => setCreateStep(goalBackStep())}>
                <Text style={s.secondaryBtnText}>{t("projects.back")}</Text>
              </Pressable>
              <Pressable
                style={[s.primaryBtn, !canCreate && s.primaryBtnDisabled]}
                disabled={!canCreate}
                onPress={() => void handleCreate()}
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

          {!error && projects.length === 0 ? (
            <View style={s.emptyState}>
              <Text style={s.emptyTitle}>{t("projects.empty_title")}</Text>
              <Text style={s.emptyBody}>{t("projects.empty_body")}</Text>
            </View>
          ) : null}

          {error ? (
            <Text style={s.empty}>{t("common.error")}</Text>
          ) : (
            projects.map((project) => (
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
    subjectText: { flex: 1, fontSize: 16, fontWeight: "600", color: C.text },
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
