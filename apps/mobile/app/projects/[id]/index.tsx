import { useCallback, useMemo, useState } from "react";
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
import { Redirect, useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { ProjectPosGroupList } from "@/components/ProjectPosGroupList";
import { ProgrammingJourney } from "@/components/ProgrammingJourney";
import { useAuth } from "@/contexts/AuthContext";
import { api, type ProjectDetail, type ProjectItem } from "@/lib/api";
import {
  isLanguageProject,
  levelLabel,
} from "@/lib/languageLevels";
import { isProgrammingStack, programmingLanguageLabel } from "@/lib/programmingLanguages";
import { buildProjectAskPrompt, buildProjectPracticePrompt, buildProjectQuizPrompt } from "@/lib/projectChat";
import {
  buildProgrammingNextUpPrompt,
  buildProgrammingStudyPrompt,
} from "@/lib/programmingStudy";
import { queueChatLaunch } from "@/lib/chatLaunch";
import { Theme, useTheme } from "@/lib/theme";

function statusIcon(item: ProjectItem): keyof typeof Ionicons.glyphMap {
  if (item.status === "mastered" || item.mastered) return "checkmark-circle";
  if (item.status === "learning") return "ellipse";
  return "ellipse-outline";
}

function statusColor(item: ProjectItem, theme: Theme): string {
  if (item.status === "mastered" || item.mastered) return theme.primary;
  if (item.status === "learning") return theme.warning;
  return theme.textTertiary;
}

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

  const load = useCallback(async () => {
    if (!token || typeof id !== "string") return;
    setLoadError(false);
    try {
      setProject(await api.getProject(token, id));
    } catch {
      setProject(null);
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [token, id]);

  const itemsByPos = useMemo(() => {
    const map = new Map<string, ProjectItem[]>();
    if (!project) return map;
    for (const group of project.by_part_of_speech ?? []) {
      map.set(group.part_of_speech, group.items);
    }
    return map;
  }, [project]);

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
            /* ignore */
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
  const isProgramming = project.kind === "programming";
  const stats = project.stats;
  const posGroups = isLang ? project.pos_groups ?? [] : [];
  const decks = isLang ? project.decks ?? [] : [];

  const promptNewDeck = () => {
    if (!token) return;
    Alert.prompt(
      t("projects.decks_title"),
      t("projects.deck_new_title"),
      async (title) => {
        const deckTitle = title?.trim();
        if (!deckTitle) return;
        Alert.prompt(t("projects.deck_add_word"), t("projects.deck_word"), async (word) => {
          const content = word?.trim();
          if (!content) return;
          try {
            await api.addProjectDeckItem(token, project.id, deckTitle, { content });
            await load();
          } catch {
            /* ignore */
          }
        });
      },
    );
  };

  const addWordToDeck = (deckTitle: string) => {
    if (!token) return;
    Alert.prompt(t("projects.deck_add_word"), t("projects.deck_word"), async (word) => {
      const content = word?.trim();
      if (!content) return;
      try {
        await api.addProjectDeckItem(token, project.id, deckTitle, { content });
        await load();
      } catch {
        /* ignore */
      }
    });
  };

  const launchChat = (prompt: string, quizLanguage?: string) => {
    queueChatLaunch(prompt, project.id, quizLanguage);
    router.replace("/");
  };

  const askRecall = () => launchChat(buildProjectAskPrompt(project));

  const quizWithRecall = () =>
    launchChat(buildProjectQuizPrompt(project), project.target_language || "en");

  const practiceWithRecall = () => launchChat(buildProjectPracticePrompt(project));

  const studyProgrammingTopic = (topic: string) =>
    launchChat(buildProgrammingStudyPrompt(project, topic));

  const continueProgramming = () => launchChat(buildProgrammingNextUpPrompt(project));

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content}>
      <View style={s.hero}>
        <View style={s.badgeRow}>
          <View style={s.badge}>
            <Text style={s.badgeText}>
              {isLang
                ? t("projects.kind.language")
                : project.kind === "programming" && isProgrammingStack(project.target_language)
                  ? programmingLanguageLabel(project.target_language)
                  : t(`projects.kind.${project.kind}`)}
            </Text>
          </View>
          {isLang ? (
            <View style={s.badge}>
              <Text style={s.badgeText}>{levelLabel(project.level)}</Text>
            </View>
          ) : project.kind === "programming" ? (
            <View style={s.badge}>
              <Text style={s.badgeText}>{t("projects.kind.programming")}</Text>
            </View>
          ) : null}
        </View>
        <Text style={s.title}>{project.title}</Text>
        {project.description ? (
          <Text style={s.description}>{project.description}</Text>
        ) : null}
        {project.kind === "programming" ? (
          <Text style={s.description}>{t("projects.kind.programming_hint")}</Text>
        ) : null}
      </View>

      <View style={s.statsGrid}>
        <View style={s.statCard}>
          <Text style={s.statValue}>{stats.mastered_count}</Text>
          <Text style={s.statLabel}>{t("projects.stats.learned")}</Text>
        </View>
        <View style={s.statCard}>
          <Text style={s.statValue}>{stats.new_count}</Text>
          <Text style={s.statLabel}>{t("projects.stats.new")}</Text>
        </View>
        <View style={s.statCard}>
          <Text style={s.statValue}>{stats.added_this_week}</Text>
          <Text style={s.statLabel}>{t("projects.stats.this_week")}</Text>
        </View>
        <View style={s.statCard}>
          <Text style={[s.statValue, stats.due_for_review > 0 && s.statHighlight]}>
            {stats.due_for_review}
          </Text>
          <Text style={s.statLabel}>{t("projects.stats.due")}</Text>
        </View>
      </View>

      {isLang ? (
        <>
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
          <Pressable style={s.studyBtn} onPress={quizWithRecall}>
            <Ionicons name="help-circle-outline" size={20} color={theme.onPrimary} />
            <Text style={s.studyBtnText}>{t("projects.quiz.start")}</Text>
          </Pressable>
        </>
      ) : isProgramming ? (
        <>
          {project.lists.length > 0 ? (
            <>
              <Pressable style={s.studyBtn} onPress={continueProgramming}>
                <Ionicons name="play-outline" size={20} color={theme.onPrimary} />
                <Text style={s.studyBtnText}>{t("projects.journey_continue")}</Text>
              </Pressable>
              <ProgrammingJourney
                lists={project.lists}
                onStudyTopic={studyProgrammingTopic}
              />
            </>
          ) : (
            <View style={s.comingSoon}>
              <ActivityIndicator color={theme.primary} />
              <Text style={s.comingSoonBody}>{t("projects.lists_empty")}</Text>
            </View>
          )}
        </>
      ) : null}

      {isLang && posGroups.length > 0 ? (
        <ProjectPosGroupList
          token={token}
          projectId={project.id}
          groups={posGroups}
          itemsByPos={itemsByPos}
        />
      ) : !isLang && !isProgramming && project.lists.length > 0 ? (
        project.lists.map((group) => (
          <View key={group.list_title} style={s.listSection}>
            <Text style={s.listTitle}>{group.list_title}</Text>
            {group.items.map((item) => (
              <View key={item.id} style={s.itemRow}>
                <Ionicons name={statusIcon(item)} size={20} color={statusColor(item, theme)} />
                <View style={s.itemMain}>
                  <Text style={s.itemContent}>{item.content}</Text>
                </View>
              </View>
            ))}
          </View>
        ))
      ) : !isProgramming && !isLang ? (
        <View style={s.practiceSection}>
          <Ionicons name="calculator-outline" size={22} color={theme.primary} />
          <Text style={s.practiceTitle}>{t("projects.practice_title")}</Text>
          <Text style={s.practiceBody}>{t("projects.practice_body")}</Text>
          <Pressable style={s.studyBtn} onPress={practiceWithRecall}>
            <Ionicons name="play-outline" size={20} color={theme.onPrimary} />
            <Text style={s.studyBtnText}>{t("projects.practice_start")}</Text>
          </Pressable>
        </View>
      ) : null}

      {isLang && stats.mastered_count > 0 && stats.total < 50 ? (
        <Text style={s.encourage}>{t("projects.encourage", { count: 10 - (stats.total % 10) })}</Text>
      ) : null}

      <Pressable style={s.chatBtn} onPress={askRecall}>
        <Ionicons name="chatbubble-ellipses-outline" size={18} color={theme.onPrimary} />
        <Text style={s.chatBtnText}>{t("projects.ask_recall")}</Text>
      </Pressable>

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
    statsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
    statCard: {
      width: "47%",
      flexGrow: 1,
      backgroundColor: theme.surface,
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
    studyBtnText: { fontSize: 16, fontWeight: "700", color: theme.onPrimary },
    studyBtnTextMuted: { color: theme.primary },
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
    chatBtn: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      backgroundColor: theme.primary,
      borderRadius: 14,
      paddingVertical: 14,
    },
    chatBtnText: { fontSize: 16, fontWeight: "700", color: theme.onPrimary },
    deleteBtn: { alignItems: "center", paddingVertical: 10 },
    deleteBtnText: { fontSize: 15, fontWeight: "600", color: theme.danger },
  });
}
