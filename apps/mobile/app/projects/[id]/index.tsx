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
import { C } from "@/constants/Colors";
import { useAuth } from "@/contexts/AuthContext";
import { api, type ProjectDetail, type ProjectItem } from "@/lib/api";
import {
  isLanguageProject,
  levelLabel,
} from "@/lib/languageLevels";
import { isProgrammingStack, programmingLanguageLabel } from "@/lib/programmingLanguages";
import { buildProjectAskPrompt, buildProjectQuizPrompt } from "@/lib/projectChat";
import {
  buildProgrammingNextUpPrompt,
  buildProgrammingStudyPrompt,
} from "@/lib/programmingStudy";
import { queueChatLaunch } from "@/lib/chatLaunch";

function statusIcon(item: ProjectItem): keyof typeof Ionicons.glyphMap {
  if (item.status === "mastered" || item.mastered) return "checkmark-circle";
  if (item.status === "learning") return "ellipse";
  return "ellipse-outline";
}

function statusColor(item: ProjectItem): string {
  if (item.status === "mastered" || item.mastered) return C.primary;
  if (item.status === "learning") return "#FF9F0A";
  return C.textTertiary;
}

export default function ProjectDetailScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [project, setProject] = useState<ProjectDetail | null>(null);

  const load = useCallback(async () => {
    if (!token || typeof id !== "string") return;
    try {
      setProject(await api.getProject(token, id));
    } catch {
      setProject(null);
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
        <ActivityIndicator color={C.primary} />
      </View>
    );
  }

  if (!project) {
    return (
      <View style={s.center}>
        <Text style={s.empty}>{t("projects.not_found")}</Text>
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

  const launchChat = (prompt: string) => {
    queueChatLaunch(prompt, project.id);
    router.replace("/");
  };

  const askRecall = () => launchChat(buildProjectAskPrompt(project));

  const quizWithRecall = () => launchChat(buildProjectQuizPrompt(project));

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
                    <Ionicons name="add-circle-outline" size={22} color={C.primary} />
                  </Pressable>
                </View>
              ))
            )}
          </View>
          <Pressable style={s.studyBtn} onPress={quizWithRecall}>
            <Ionicons name="help-circle-outline" size={20} color="#fff" />
            <Text style={s.studyBtnText}>{t("projects.quiz.start")}</Text>
          </Pressable>
        </>
      ) : isProgramming ? (
        <>
          {project.lists.length > 0 ? (
            <>
              <Pressable style={s.studyBtn} onPress={continueProgramming}>
                <Ionicons name="play-outline" size={20} color="#fff" />
                <Text style={s.studyBtnText}>{t("projects.journey_continue")}</Text>
              </Pressable>
              <ProgrammingJourney
                lists={project.lists}
                onStudyTopic={studyProgrammingTopic}
              />
            </>
          ) : (
            <View style={s.comingSoon}>
              <ActivityIndicator color={C.primary} />
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
                <Ionicons name={statusIcon(item)} size={20} color={statusColor(item)} />
                <View style={s.itemMain}>
                  <Text style={s.itemContent}>{item.content}</Text>
                </View>
              </View>
            ))}
          </View>
        ))
      ) : !isProgramming ? (
        <View style={s.comingSoon}>
          <Ionicons name="sparkles-outline" size={22} color={C.primary} />
          <Text style={s.comingSoonTitle}>{t("projects.coming_title")}</Text>
          <Text style={s.comingSoonBody}>{t("projects.lists_empty")}</Text>
        </View>
      ) : null}

      {isLang && stats.mastered_count > 0 && stats.total < 50 ? (
        <Text style={s.encourage}>{t("projects.encourage", { count: 10 - (stats.total % 10) })}</Text>
      ) : null}

      <Pressable style={s.chatBtn} onPress={askRecall}>
        <Ionicons name="chatbubble-ellipses-outline" size={18} color="#fff" />
        <Text style={s.chatBtnText}>{t("projects.ask_recall")}</Text>
      </Pressable>

      <Pressable style={s.deleteBtn} onPress={confirmDelete}>
        <Text style={s.deleteBtnText}>{t("projects.delete")}</Text>
      </Pressable>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: C.bg },
  content: { padding: 16, gap: 16, paddingBottom: 40 },
  empty: { fontSize: 15, color: C.textSecondary },
  hero: { gap: 8 },
  badgeRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  badge: {
    backgroundColor: C.primaryLight,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  badgeText: { fontSize: 12, fontWeight: "700", color: C.primary },
  title: { fontSize: 28, fontWeight: "800", color: C.text, letterSpacing: -0.5 },
  description: { fontSize: 16, lineHeight: 24, color: C.textSecondary },
  statsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  statCard: {
    width: "47%",
    flexGrow: 1,
    backgroundColor: C.surface,
    borderRadius: 14,
    padding: 14,
    alignItems: "center",
    gap: 4,
  },
  statValue: { fontSize: 22, fontWeight: "800", color: C.text },
  statHighlight: { color: C.primary },
  statLabel: { fontSize: 11, fontWeight: "600", color: C.textSecondary, textAlign: "center" },
  studyBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: C.primary,
    borderRadius: 14,
    paddingVertical: 14,
  },
  studyBtnMuted: { backgroundColor: C.primaryLight },
  studyBtnText: { fontSize: 16, fontWeight: "700", color: "#fff" },
  studyBtnTextMuted: { color: C.primary },
  listSection: {
    backgroundColor: C.surface,
    borderRadius: 16,
    padding: 14,
    gap: 10,
  },
  listTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: C.textTertiary,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  itemRow: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
  itemMain: { flex: 1, gap: 2 },
  itemTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  itemContent: { fontSize: 16, fontWeight: "700", color: C.text, flex: 1 },
  itemMastered: { color: C.textSecondary, textDecorationLine: "line-through" },
  itemDef: { fontSize: 14, color: C.textSecondary },
  itemNote: { fontSize: 13, lineHeight: 18, color: C.textSecondary, fontStyle: "italic" },
  itemMeta: { fontSize: 11, fontWeight: "600", color: C.textTertiary, marginTop: 2 },
  comingSoon: {
    backgroundColor: C.surface,
    borderRadius: 16,
    padding: 16,
    gap: 8,
  },
  comingSoonTitle: { fontSize: 16, fontWeight: "700", color: C.text },
  comingSoonBody: { fontSize: 14, lineHeight: 21, color: C.textSecondary },
  encourage: {
    fontSize: 14,
    lineHeight: 20,
    color: C.primary,
    fontWeight: "600",
    textAlign: "center",
  },
  decksSection: {
    backgroundColor: C.surface,
    borderRadius: 16,
    padding: 14,
    gap: 10,
  },
  decksHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  decksTitle: { fontSize: 13, fontWeight: "700", color: C.textSecondary, textTransform: "uppercase" },
  decksLink: { fontSize: 13, fontWeight: "600", color: C.primary },
  decksEmpty: { fontSize: 14, color: C.textSecondary, lineHeight: 20 },
  deckRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  deckMain: { flex: 1, gap: 2 },
  deckTitle: { fontSize: 16, fontWeight: "700", color: C.text },
  deckMeta: { fontSize: 13, color: C.textSecondary },
  chatBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: C.primary,
    borderRadius: 14,
    paddingVertical: 14,
  },
  chatBtnText: { fontSize: 16, fontWeight: "700", color: "#fff" },
  deleteBtn: { alignItems: "center", paddingVertical: 10 },
  deleteBtnText: { fontSize: 15, fontWeight: "600", color: C.danger },
});
