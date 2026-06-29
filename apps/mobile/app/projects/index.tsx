import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { useProjects } from "@/contexts/ProjectsContext";
import { api, type LanguageLevel, type ProjectKind } from "@/lib/api";
import { LANGUAGE_LEVELS, levelLabel } from "@/lib/languageLevels";
import {
  DEFAULT_PROGRAMMING_LANGUAGE,
  PROGRAMMING_LANGUAGES,
  programmingLanguageLabel,
  type ProgrammingLanguageId,
} from "@/lib/programmingLanguages";
import { Theme, useTheme } from "@/lib/theme";

const SUBJECTS: ProjectKind[] = ["language", "math", "programming"];

type CreateStep = "subject" | "level" | "stack" | "goal";

function kindIcon(kind: ProjectKind): keyof typeof Ionicons.glyphMap {
  if (kind === "language" || kind === "vocabulary") return "language-outline";
  if (kind === "programming") return "code-slash-outline";
  if (kind === "math") return "calculator-outline";
  return "folder-outline";
}

function subjectKind(kind: ProjectKind): ProjectKind {
  return kind === "vocabulary" ? "language" : kind;
}

function learningTitle(
  kind: ProjectKind,
  level: LanguageLevel,
  programmingLanguage: ProgrammingLanguageId,
  description: string,
  t: (key: string) => string,
): string {
  const goal = description.trim();
  if (goal.length > 0) {
    const firstLine = goal.split("\n")[0]?.trim() ?? goal;
    if (firstLine.length <= 80) return firstLine;
    return `${firstLine.slice(0, 77)}…`;
  }
  if (kind === "language") {
    return `${t("projects.kind.language")} · ${levelLabel(level)}`;
  }
  if (kind === "programming") {
    return `${programmingLanguageLabel(programmingLanguage)} · ${t("projects.kind.programming")}`;
  }
  return t(`projects.kind.${subjectKind(kind)}`);
}

function goalStepHint(
  kind: ProjectKind,
  level: LanguageLevel,
  programmingLanguage: ProgrammingLanguageId,
  t: (key: string) => string,
): string {
  if (kind === "language") {
    return `${t("projects.kind.language")} · ${levelLabel(level)}`;
  }
  if (kind === "programming") {
    return `${programmingLanguageLabel(programmingLanguage)} · ${t("projects.kind.programming")}`;
  }
  return t(`projects.kind.${subjectKind(kind)}`);
}

function projectRowMeta(
  project: { kind: ProjectKind; level: LanguageLevel; target_language: string },
  t: (key: string) => string,
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

function goalPlaceholderKey(kind: ProjectKind): string {
  if (kind === "language" || kind === "vocabulary") return "projects.goal_placeholder_english";
  if (kind === "math") return "projects.goal_placeholder_math";
  return "projects.goal_placeholder_programming";
}

export default function ProjectsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const router = useRouter();
  const { projects, loading, error, refresh, setProjects } = useProjects();
  const [createStep, setCreateStep] = useState<CreateStep | null>(null);
  const [descriptionInput, setDescriptionInput] = useState("");
  const [kind, setKind] = useState<ProjectKind>("language");
  const [level, setLevel] = useState<LanguageLevel>("level1");
  const [programmingLanguage, setProgrammingLanguage] = useState<ProgrammingLanguageId>(
    DEFAULT_PROGRAMMING_LANGUAGE,
  );
  const [levelPickerOpen, setLevelPickerOpen] = useState(false);

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: projects.length > 0 });
    }, [refresh, projects.length]),
  );

  if (!token) return <Redirect href="/login" />;

  const resetCreate = () => {
    setCreateStep(null);
    setDescriptionInput("");
    setKind("language");
    setLevel("level1");
    setProgrammingLanguage(DEFAULT_PROGRAMMING_LANGUAGE);
    setLevelPickerOpen(false);
  };

  const selectSubject = (next: ProjectKind) => {
    setKind(next);
    if (next === "language") setCreateStep("level");
    else if (next === "programming") setCreateStep("stack");
    else setCreateStep("goal");
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

  const handleCreate = async () => {
    const description = descriptionInput.trim();
    if (!description || !token) return;
    const title = learningTitle(kind, level, programmingLanguage, description, t);
    try {
      const project = await api.createProject(token, {
        title,
        description,
        kind,
        level,
        target_language: kind === "programming" ? programmingLanguage : "en",
      });
      resetCreate();
      setProjects((prev) => [project, ...prev]);
      router.push(`/projects/${project.id}`);
    } catch {
      /* ignore */
    }
  };

  const canCreate = descriptionInput.trim().length > 0;

  return (
    <View style={s.root}>
      {loading ? (
        <View style={s.center}>
          <ActivityIndicator color={C.primary} />
        </View>
      ) : (
        <ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
          {createStep !== null ? (
            <View style={s.createCard}>
              {createStep === "subject" ? (
                <>
                  <Text style={s.createLabel}>{t("projects.what_to_learn")}</Text>
                  <View style={s.subjectList}>
                    {SUBJECTS.map((item) => {
                      const active = kind === item;
                      return (
                        <Pressable
                          key={item}
                          style={[s.subjectRow, active && s.subjectRowActive]}
                          onPress={() => selectSubject(item)}
                        >
                          <View style={s.subjectIcon}>
                            <Ionicons name={kindIcon(item)} size={22} color={C.primary} />
                          </View>
                          <Text style={[s.subjectText, active && s.subjectTextActive]}>
                            {t(`projects.kind.${item}`)}
                          </Text>
                          <Ionicons name="chevron-forward" size={18} color={C.textTertiary} />
                        </Pressable>
                      );
                    })}
                  </View>
                  <Pressable style={s.secondaryBtn} onPress={resetCreate}>
                    <Text style={s.secondaryBtnText}>{t("common.cancel")}</Text>
                  </Pressable>
                </>
              ) : null}

              {createStep === "level" ? (
                <>
                  <Text style={s.createLabel}>{t("projects.level_label")}</Text>
                  <Text style={s.stepHint}>{t("projects.level_hint")}</Text>
                  <Pressable style={s.dropdown} onPress={() => setLevelPickerOpen(true)}>
                    <Text style={s.dropdownText}>{levelLabel(level)}</Text>
                    <Ionicons name="chevron-down" size={18} color={C.textSecondary} />
                  </Pressable>
                  <View style={s.createActions}>
                    <Pressable style={s.secondaryBtn} onPress={() => setCreateStep("subject")}>
                      <Text style={s.secondaryBtnText}>{t("projects.back")}</Text>
                    </Pressable>
                    <Pressable style={s.primaryBtn} onPress={() => setCreateStep("goal")}>
                      <Text style={s.primaryBtnText}>{t("projects.next")}</Text>
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

              {createStep === "goal" ? (
                <>
                  <Text style={s.createLabel}>{t("projects.step_goal")}</Text>
                  <Text style={s.stepHint}>
                    {goalStepHint(kind, level, programmingLanguage, t)}
                  </Text>
                  <Text style={s.fieldLabel}>{t("projects.goal_hint")}</Text>
                  <TextInput
                    style={[s.input, s.inputMultiline]}
                    placeholder={t(goalPlaceholderKey(kind))}
                    placeholderTextColor={C.textTertiary}
                    value={descriptionInput}
                    onChangeText={setDescriptionInput}
                    multiline
                    autoFocus
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
                      <Text style={s.primaryBtnText}>{t("projects.create")}</Text>
                    </Pressable>
                  </View>
                </>
              ) : null}
            </View>
          ) : (
            <Pressable style={s.newProjectBtn} onPress={() => setCreateStep("subject")}>
              <Ionicons name="add-circle-outline" size={22} color={C.primary} />
              <Text style={s.newProjectText}>{t("projects.add_learning")}</Text>
            </Pressable>
          )}

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

      <Modal visible={levelPickerOpen} transparent animationType="fade">
        <View style={s.modalBackdrop}>
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setLevelPickerOpen(false)} />
          <View style={s.modalSheet}>
            <Text style={s.modalTitle}>{t("projects.level_label")}</Text>
            {LANGUAGE_LEVELS.map((item) => (
              <Pressable
                key={item}
                style={[s.modalOption, level === item && s.modalOptionActive]}
                onPress={() => {
                  setLevel(item);
                  setLevelPickerOpen(false);
                }}
              >
                <Text style={[s.modalOptionText, level === item && s.modalOptionTextActive]}>
                  {levelLabel(item)}
                </Text>
                {level === item ? (
                  <Ionicons name="checkmark" size={18} color={C.primary} />
                ) : null}
              </Pressable>
            ))}
          </View>
        </View>
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
    createCard: {
      backgroundColor: C.surface,
      borderRadius: 16,
      padding: 16,
      gap: 10,
    },
    createLabel: { fontSize: 17, fontWeight: "700", color: C.text },
    stepHint: { fontSize: 14, color: C.textSecondary, marginBottom: 4 },
    subjectList: { gap: 8 },
    subjectRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingVertical: 14,
      paddingHorizontal: 12,
      borderRadius: 14,
      backgroundColor: C.bg,
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
      backgroundColor: C.surface,
      alignItems: "center",
      justifyContent: "center",
    },
    subjectText: { flex: 1, fontSize: 16, fontWeight: "600", color: C.text },
    subjectTextActive: { color: C.primaryDark },
    input: {
      backgroundColor: C.bg,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: C.border,
      paddingHorizontal: 12,
      paddingVertical: 10,
      fontSize: 16,
      color: C.text,
    },
    inputMultiline: { minHeight: 96, textAlignVertical: "top" },
    dropdown: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      backgroundColor: C.bg,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: C.border,
      paddingHorizontal: 12,
      paddingVertical: 14,
    },
    dropdownText: { fontSize: 16, fontWeight: "600", color: C.text },
    createActions: { flexDirection: "row", gap: 10, marginTop: 4 },
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
    },
    primaryBtnDisabled: { opacity: 0.45 },
    primaryBtnText: { fontSize: 15, fontWeight: "700", color: "#fff" },
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
    modalBackdrop: {
      flex: 1,
      backgroundColor: "rgba(0,0,0,0.35)",
      justifyContent: "flex-end",
    },
    modalSheet: {
      backgroundColor: C.surface,
      borderTopLeftRadius: 20,
      borderTopRightRadius: 20,
      padding: 16,
      paddingBottom: 32,
      gap: 4,
    },
    modalTitle: {
      fontSize: 13,
      fontWeight: "700",
      color: C.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
      marginBottom: 8,
    },
    modalOption: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingVertical: 14,
      paddingHorizontal: 8,
      borderRadius: 12,
    },
    modalOptionActive: { backgroundColor: C.primaryLight },
    modalOptionText: { flex: 1, fontSize: 16, fontWeight: "600", color: C.text },
    modalOptionTextActive: { color: C.primary },
    fieldLabel: {
      fontSize: 14,
      fontWeight: "600",
      color: C.textSecondary,
      marginTop: 2,
    },
  });
}
