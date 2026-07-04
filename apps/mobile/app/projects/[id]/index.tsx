import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { ProjectPosGroupList } from "@/components/ProjectPosGroupList";
import { ProjectProgressHero } from "@/components/ProjectProgressHero";
import { ProjectItemRow } from "@/components/ProjectItemRow";
import { useAuth } from "@/contexts/AuthContext";
import { api, type ProjectDetail, type VocabStatus } from "@/lib/api";
import { queueChatLaunch } from "@/lib/chatLaunch";
import {
  isLanguageProject,
  levelLabel,
} from "@/lib/languageLevels";
import { resolveDailyGoal } from "@/lib/dailyGoals";
import {
  buildProjectChatTutorPrompt,
  buildProjectBonusWordsPrompt,
  isDailyGoalMet,
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
  const [conceptBusyId, setConceptBusyId] = useState<string | null>(null);

  // Cross-platform prompt replacement for Alert.prompt (iOS-only). Deck create
  // and add-word flows use this Modal+TextInput so they work on Android too.
  const [promptVisible, setPromptVisible] = useState(false);
  const [promptValue, setPromptValue] = useState("");
  const [promptConfig, setPromptConfig] = useState<{
    title: string;
    message?: string;
    placeholder?: string;
    onSubmit: (value: string) => void | Promise<void>;
  } | null>(null);

  const showPrompt = useCallback(
    (
      title: string,
      message: string | undefined,
      placeholder: string | undefined,
      onSubmit: (value: string) => void | Promise<void>,
    ) => {
      setPromptConfig({ title, message, placeholder, onSubmit });
      setPromptValue("");
      setPromptVisible(true);
    },
    [],
  );

  const submitPrompt = useCallback(async () => {
    const cfg = promptConfig;
    setPromptVisible(false);
    setPromptConfig(null);
    const value = promptValue.trim();
    setPromptValue("");
    if (cfg && value) {
      try {
        await cfg.onSubmit(value);
      } catch {
        Alert.alert(t("common.error"), t("projects.add_word_failed"));
      }
    }
  }, [promptConfig, promptValue, t]);

  const cancelPrompt = useCallback(() => {
    setPromptVisible(false);
    setPromptConfig(null);
    setPromptValue("");
  }, []);

  const load = useCallback(async () => {
    if (!token || typeof id !== "string") return;
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
      setLoading(false);
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

  if (loading) {
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
  const posGroups = isLang ? project.pos_groups ?? [] : [];
  const decks = isLang ? project.decks ?? [] : [];

  const promptNewDeck = () => {
    if (!token) return;
    // Two-step: deck title, then first word. Chain via showPrompt.
    showPrompt(
      t("projects.decks_title"),
      t("projects.deck_new_title"),
      t("projects.deck_new_title"),
      (deckTitle) => {
        showPrompt(
          t("projects.deck_add_word"),
          t("projects.deck_word"),
          t("projects.deck_word"),
          async (content) => {
            await api.addProjectDeckItem(token, project.id, deckTitle, { content });
            await load();
          },
        );
      },
    );
  };

  const addWordToDeck = (deckTitle: string) => {
    if (!token) return;
    showPrompt(
      t("projects.deck_add_word"),
      t("projects.deck_word"),
      t("projects.deck_word"),
      async (content) => {
        await api.addProjectDeckItem(token, project.id, deckTitle, { content });
        await load();
      },
    );
  };

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

  const startTriviaQuiz = () => {
    if (!project || !isTrivia) return;
    router.push(`/projects/${project.id}/quiz`);
  };

  const startTriviaChat = () => {
    if (!project || !isTrivia) return;
    queueChatLaunch(buildProjectChatTutorPrompt(project), project.id, undefined, "trivia", "chat");
    router.replace("/");
  };

  const startLanguageSession = () => {
    if (!project || !isLang) return;
    queueChatLaunch(buildProjectChatTutorPrompt(project), project.id, "en", "vocab", "chat");
    router.replace("/");
  };

  const startLanguageExam = () => {
    if (!project || !isLang) return;
    router.push(`/projects/${project.id}/quiz`);
  };

  const startLanguageBonus = () => {
    if (!project || !isLang) return;
    queueChatLaunch(buildProjectBonusWordsPrompt(project), project.id, "en");
    router.replace("/");
  };

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content}>
      <View style={s.hero}>
        <View style={s.badgeRow}>
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
        <Text style={s.title}>{project.title}</Text>
        {isTrivia ? (
          <Text style={s.description}>
            {formatTriviaTopicLabels(parseTriviaTopics(project.description), t)}
          </Text>
        ) : project.description ? (
          <Text style={s.description}>{project.description}</Text>
        ) : null}
        {isTrivia ? (
          <Text style={s.description}>{t("projects.trivia.detail_hint")}</Text>
        ) : null}
      </View>

      <ProjectProgressHero
        stats={stats}
        learnedLabel={statLabels.learned}
        dueLabel={statLabels.due}
        dailyGoal={dailyGoal}
      />

      {isLang && dailyGoalMet ? (
        <View style={s.doneBanner}>
          <Ionicons name="checkmark-circle" size={22} color={theme.primary} />
          <Text style={s.doneBannerText}>
            {t("projects.daily_goal_done_hint", { goal: dailyGoal })}
          </Text>
        </View>
      ) : null}

      {isLang ? (
        dailyGoalMet ? (
          <Pressable style={[s.studyBtn, s.studyBtnMuted]} onPress={startLanguageBonus}>
            <Ionicons name="add-circle-outline" size={20} color={theme.primary} />
            <Text style={[s.studyBtnText, s.studyBtnTextMuted]}>
              {t("projects.add_bonus_words")}
            </Text>
          </Pressable>
        ) : (
          <>
            <Pressable style={s.studyBtn} onPress={startLanguageSession}>
              <Ionicons name="chatbubble-ellipses-outline" size={20} color={theme.onPrimary} />
              <Text style={s.studyBtnText}>{t("projects.learn_in_chat")}</Text>
            </Pressable>
            <Pressable style={[s.studyBtn, s.studyBtnOutline]} onPress={startLanguageExam}>
              <Ionicons name="school-outline" size={20} color={theme.primary} />
              <Text style={[s.studyBtnText, s.studyBtnTextMuted]}>{t("projects.take_quiz")}</Text>
            </Pressable>
          </>
        )
      ) : null}

      {isTrivia ? (
        <>
          <Pressable style={s.studyBtn} onPress={startTriviaChat}>
            <Ionicons name="chatbubble-ellipses-outline" size={20} color={theme.onPrimary} />
            <Text style={s.studyBtnText}>{t("projects.learn_in_chat")}</Text>
          </Pressable>
          <Pressable style={[s.studyBtn, s.studyBtnOutline]} onPress={startTriviaQuiz}>
            <Ionicons name="school-outline" size={20} color={theme.primary} />
            <Text style={[s.studyBtnText, s.studyBtnTextMuted]}>{t("projects.take_quiz")}</Text>
          </Pressable>
        </>
      ) : null}

      {isLang && posGroups.length > 0 ? (
        <ProjectPosGroupList
          token={token}
          projectId={project.id}
          groups={posGroups}
          onItemUpdated={load}
        />
      ) : null}

      {isLang ? (
        <View style={s.decksSection}>
            <View style={s.decksHeader}>
              <Text style={s.decksTitle}>{t("projects.decks_title")}</Text>
              <Pressable onPress={promptNewDeck} hitSlop={8}>
                <Text style={s.decksLink}>+ {t("projects.deck_add_word")}</Text>
              </Pressable>
            </View>
            {decks.length === 0 ? (
              <Text style={s.decksEmpty}>{t("projects.decks_empty")}</Text>
            ) : (
              decks.map((deck) => (
                <View key={deck.title} style={s.deckRow}>
                  <View style={s.deckMain}>
                    <Text style={s.deckTitle}>{deck.title}</Text>
                    <Text style={s.deckMeta}>{deck.count} words</Text>
                  </View>
                  <Pressable onPress={() => addWordToDeck(deck.title)} hitSlop={8}>
                    <Ionicons name="add-circle-outline" size={22} color={theme.primary} />
                  </Pressable>
                </View>
              ))
            )}
          </View>
      ) : isConcept ? (
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

      {isLang && stats.mastered_count > 0 && stats.total < 50 ? (
        <Text style={s.encourage}>{t("projects.encourage", { count: 10 - (stats.total % 10) })}</Text>
      ) : null}

      <Pressable style={s.deleteBtn} onPress={confirmDelete}>
        <Text style={s.deleteBtnText}>{t("projects.delete")}</Text>
      </Pressable>

      {/*
        Cross-platform prompt modal (replaces iOS-only Alert.prompt for the
        deck create / add-word flows so they work on Android).
      */}
      <Modal
        visible={promptVisible}
        transparent
        animationType="fade"
        onRequestClose={cancelPrompt}
      >
        <Pressable style={s.promptOverlay} onPress={cancelPrompt}>
          <Pressable style={s.promptCard} onPress={(e) => e.stopPropagation()}>
            <Text style={s.promptTitle}>{promptConfig?.title}</Text>
            {promptConfig?.message ? (
              <Text style={s.promptMessage}>{promptConfig.message}</Text>
            ) : null}
            <TextInput
              style={s.promptInput}
              value={promptValue}
              onChangeText={setPromptValue}
              placeholder={promptConfig?.placeholder}
              placeholderTextColor={theme.textTertiary}
              autoFocus
              returnKeyType="done"
              onSubmitEditing={submitPrompt}
            />
            <View style={s.promptActions}>
              <Pressable style={s.promptAction} onPress={cancelPrompt}>
                <Text style={s.promptActionText}>{t("common.cancel")}</Text>
              </Pressable>
              <Pressable
                style={[s.promptAction, s.promptActionPrimary]}
                onPress={submitPrompt}
              >
                <Text style={[s.promptActionText, s.promptActionPrimaryText]}>
                  {t("common.add")}
                </Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
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
    badgeRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    badge: {
      backgroundColor: theme.primaryLight,
      borderRadius: 999,
      paddingHorizontal: 10,
      paddingVertical: 4,
    },
    badgeText: { fontSize: 12, fontWeight: "700", color: theme.primary },
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
    studyBtn: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      backgroundColor: theme.primary,
      borderRadius: 14,
      paddingVertical: 14,
    },
    studyBtnMuted: { backgroundColor: theme.primaryLight },
    studyBtnOutline: {
      backgroundColor: theme.surface,
      borderWidth: 1.5,
      borderColor: theme.primary,
      marginTop: 10,
    },
    studyBtnText: { fontSize: 16, fontWeight: "700", color: theme.onPrimary },
    studyBtnTextMuted: { color: theme.primary },
    doneBanner: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 10,
      backgroundColor: theme.primaryLight,
      borderRadius: 14,
      padding: 14,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    doneBannerText: {
      flex: 1,
      fontSize: 14,
      lineHeight: 20,
      fontWeight: "600",
      color: theme.textSecondary,
    },
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
    encourage: {
      fontSize: 14,
      lineHeight: 20,
      color: theme.primary,
      fontWeight: "600",
      textAlign: "center",
    },
    decksSection: {
      backgroundColor: theme.surface,
      borderRadius: 16,
      padding: 14,
      gap: 10,
    },
    decksHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
    decksTitle: { fontSize: 13, fontWeight: "700", color: theme.textSecondary, textTransform: "uppercase" },
    decksLink: { fontSize: 13, fontWeight: "600", color: theme.primary },
    decksEmpty: { fontSize: 14, color: theme.textSecondary, lineHeight: 20 },
    deckRow: { flexDirection: "row", alignItems: "center", gap: 10 },
    deckMain: { flex: 1, gap: 2 },
    deckTitle: { fontSize: 16, fontWeight: "700", color: theme.text },
    deckMeta: { fontSize: 13, color: theme.textSecondary },
    deleteBtn: { alignItems: "center", paddingVertical: 10 },
    deleteBtnText: { fontSize: 15, fontWeight: "600", color: theme.danger },
    promptOverlay: {
      flex: 1,
      backgroundColor: theme.scrim,
      justifyContent: "center",
      padding: 28,
    },
    promptCard: {
      backgroundColor: theme.surface,
      borderRadius: 16,
      padding: 18,
      gap: 12,
    },
    promptTitle: { fontSize: 16, fontWeight: "700", color: theme.text },
    promptMessage: { fontSize: 14, color: theme.textSecondary, lineHeight: 20 },
    promptInput: {
      borderWidth: 1,
      borderColor: theme.border,
      borderRadius: 10,
      paddingHorizontal: 12,
      paddingVertical: 10,
      fontSize: 16,
      color: theme.text,
    },
    promptActions: { flexDirection: "row", justifyContent: "flex-end", gap: 8 },
    promptAction: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10 },
    promptActionPrimary: { backgroundColor: theme.primary },
    promptActionText: { fontSize: 15, fontWeight: "600", color: theme.textSecondary },
    promptActionPrimaryText: { color: theme.onPrimary },
  });
}
